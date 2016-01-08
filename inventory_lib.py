#!/usr/bin/env python3

import logging
import subprocess
import distutils.util
import types
import re
from collections import defaultdict
import json
import os
import tempfile

# use termcolor when available, otherwise ignore
try:
    from termcolor import colored
except ImportError:
    def colored(text, col):
        return text

# our modules
from dnsvs import dnsvs_ssh
from config import configinstance as Config



class Hostlist:

    def __init__(self, source='file'):
        self.generator = source
        self.hostlist = []
        if source == 'file':
            self.add_hosts_from_files()
        elif source == 'dnsvs':
            self.add_hosts_from_dnsvs()
        else:
            raise Exception('unsupported hostlist source: '+str(source))

    def add_hosts_from_files(self):
        for source in Config["sources"]:
            for group in Config["groups"]:
                self.add_hostfile(source, group)

    def add_hostfile(self, source, group):
        fname = Config["hostlistdir"] + source + "." + group
        try:
            infile = open(fname)
        except:
            logging.error('file missing %s' % fname)
            return
        content = infile.readlines()
        for line in content:
            try:
                if line.strip():
                    self.hostlist.append(Host('confline', line, source, group))
            except:
                logging.error("Failed to parse host (%s) in %s." % (line, infile))
                raise

    def add_hosts_from_dnsvs(self):
        con = dnsvs_ssh.dnsvs_interface()

        for namespace in Config['dnsvs']['namespaces']:
            hosts = con.get_hosts(namespace)
            for hostname, ip in hosts.items():
                self.hostlist.append(Host('hostip', hostname, ip))

    def __str__(self):
        return '\n'.join([str(h) for h in self.hostlist])

    def check_consistency(self):
        self.check_duplicates()
        self.check_missing_mac_ip()
        logging.info("consistency check finished")

    def check_duplicates(self):
        """check consistency of hostlist

        detect duplicates (ip, mac, hostname)"""

        inverselist = {}
        tocheck_props = ['ip', 'mac', 'hostname']
        for prop in tocheck_props:
            inverselist[prop] = {}
            for host in self.hostlist:
                myhostprop = getattr(host, prop)
                if myhostprop is None:
                    continue
                if myhostprop in inverselist[prop]:
                    logging.error("Found duplicate %s for hosts \n%s\n%s"
                                  % (prop, inverselist[prop][myhostprop], host))
                inverselist[prop][myhostprop] = host

    def check_missing_mac_ip(self):
        """check if hosts are missing an ip or mac"""

        for host in self.hostlist:
            if not host.grsource in Config['groups_without_ip']:
                if host.ip is None:
                    logging.error("Missing IP in %s " % host)

        if self.generator == 'file':
            for host in self.hostlist:
                if not host.grsource in Config['groups_without_mac']:
                    if host.mac is None:
                        logging.error("Missing MAC in %s " % host)

    def diff(self, otherhostlist):
        diff = types.SimpleNamespace()
        diff.add, diff.remove = [], []
        hostnames = {h.fqdn: h.ip for h in self.hostlist if h.ip is not None}
        inversehostlist = {h.fqdn: h for h in self.hostlist}

        otherhostnames = {h.fqdn: h.ip for h in otherhostlist.hostlist if h.ip is not None}
        inverseotherhostlist = {h.fqdn: h for h in otherhostlist.hostlist}

        for h, ip in hostnames.items():
            if h not in otherhostnames or otherhostnames[h] != hostnames[h]:
                diff.add.append(inversehostlist[h])
        for h, ip in otherhostnames.items():
            if h not in hostnames or otherhostnames[h] != hostnames[h]:
                diff.remove.append(inverseotherhostlist[h])

        diff.empty = (not diff.add) and (not diff.remove)
        return diff

    def apply_diff(self, diff):
        con = dnsvs_ssh.dnsvs_interface()
        for host in diff.remove:
            logging.info('removing\t'+str(host))
            con.remove_host(host)
        for host in diff.add:
            logging.info('adding\t'+str(host))
            con.add_host(host)

    def print_diff(self, diff):
        if diff.add:
            print(colored("Only in local files: ", 'green'))
            for h in sorted(diff.add, key=lambda h: h.fqdn):
                print(colored('+'+str(h), 'green'))
        if diff.remove:
            print(colored("Only in DNSVS: ", 'red'))
            for h in sorted(diff.remove, key=lambda h: h.fqdn):
                print(colored('-'+str(h), 'red'))

    def make_dhcp(self):
        with open(Config["dhcp"]["header"]) as f:
            header = f.read()
        dhcpout = ""
        for host in self.hostlist:
            entry = host.dhcp
            if entry:
                dhcpout += entry + '\n'
        self.write(header+dhcpout, Config["dhcp"]["build"])

    def make_ansible(self):
        resultdict = defaultdict(list)
        hostvars = {}
        for host in self.hostlist:
            if not host.extravars['ansible'] \
                    or host.source in Config['no_ansible_hosts']:
                continue
            ans = host.ansible
            hostvars[ans['hostname']] = ans['vars']
            for groupname in ans['groups']:
                resultdict[groupname] += [ans['hostname']]

        resultdict['_meta'] = {'hostvars': hostvars}

        jsonout = json.dumps(resultdict, sort_keys=True, indent=4)
        return jsonout

    def make_munin(self):
        hostnames = [h.fqdn
                     for h in self.hostlist
                     if h.source not in Config['no_ansible_hosts']]
        fcont = ''
        for host in hostnames:
            fcont += '[{h}]\naddress {h}\n'.format(h=host)
        self.write(fcont, Config["munin"]["build"])

    def make_hosts(self):
        content = '\n'.join(host.host for host in self.hostlist if host.host is not None)
        self.write(content, Config["hosts"]["build"])


    def _ssh_keyscan_to_hash(self, indata):
        hosts = {}
        for l in indata.splitlines():
            fields = l.split()
            hosts[(fields[0], fields[1])] = fields[2]
        return hosts

    def make_ssh_known_hosts(self):
        aliases = [a.encode()
                   for host in self.hostlist
                   for a in host.aliases
                   if host.ip]

        with tempfile.NamedTemporaryFile() as f:
            f.file.write(b"\n".join(aliases))
            f.file.flush()
            p = subprocess.Popen(['ssh-keyscan', '-T', '1', '-f', f.name],
                    stderr=subprocess.DEVNULL, stdout=subprocess.PIPE, bufsize=-1)
            logging.info("started ssh session")
            out, err = p.communicate()
            logging.info("communicated with hosts")
            newhosts = self._ssh_keyscan_to_hash(out.decode())
            oldout = ""
            with open(Config["ssh"]["import"]) as previousf:
                oldout = previousf.read()
            hosts = self._ssh_keyscan_to_hash(oldout)
            hosts.update(newhosts)

            sorted_hosts = sorted(hosts, key=lambda x: x[0]+' '+x[1])
            fcont = '\n'.join(
                [' '.join((k[0], k[1], hosts[k])) for k in sorted_hosts]
            )
            self.write(fcont, Config["ssh"]["build"])
            logging.debug("wrote ssh hostkeys to file")

    def write(self, content, buildname):
        builddir = Config["builddir"]
        if not os.path.isdir(builddir):
            os.mkdir(builddir)
        fname = builddir + buildname
        with open(fname, 'w') as f:
            f.write(content)


class Host:
    """
    Representation of one host with several properties
    """

    def __init__(self, type, *args):
        self.source = ""
        self.group = ""
        self.ip = None
        self.mac = None
        self.hostname = None
        if type == 'hostip':
            self._init_hostname_ip(*args)
        elif type == 'confline':
            self._init_confline(*args)
        else:
            raise Exception("wrong type argument")

    def _init_common(self):
        self.extravars = {
            'ansible': True,
            'ssh': True
        }
        self.ip = None
        self.mac = None
        self.hostname = ""

    def _init_hostname_ip(self, hostname, ip):
        self._init_common()
        self.ip = ip
        self.hostname = hostname
        self.check_input_format()
        self.set_fqdn()

    def _init_confline(self, confline, source, group):
        """
        parses a config file line of the form
        #host=host1.abc.kit.edu        hwadress=00:12:34:ab:cd:ef      ipadress=127.0.0.1
        """
        self._init_common()
        self.source = source
        self.group = group
        varslist = {
            'ansible': bool,
            'subnet': str,
            'ssh': bool,
        }
        ansiblevarlist = ['subnet']
        uncommented = confline.split('#', 1)[0]
        params = filter(None, uncommented.split())
        for p in params:
            a, b = p.split('=')
            if a == 'host':
                self.hostname = b
            elif a == 'mac':
                self.mac = b.lower()
            elif a == 'ip':
                self.ip = b
            elif a in varslist:
                if varslist[a] == bool:
                    self.extravars[a] = distutils.util.strtobool(b)
                elif varslist[a] == str:
                    self.extravars[a] = b
                else:
                    raise NotImplemented("Unknown type " + varslist[a] + " for input " + a)
            else:
                logging.error("unexpected parameter name %s" % a)
                raise Exception
        if self.hostname is "":
            logging.error("no hostname given for "+str(self))
            raise Exception
        self.ansiblevars = {
            k: self.extravars[k]
            for k in ansiblevarlist
            if k in self.extravars
        }
        self.check_input_format()
        self.set_fqdn()

    def set_fqdn(self):
        if self.hostname.endswith(Config["domain"]):
            dot_parts = self.hostname.split('.')
            self.prefix = dot_parts[0]
            self.domain = '.'.join(dot_parts[1:])
            self.fqdn = self.hostname
        else:
            self.prefix = self.hostname
            self.domain = self.get_domain(self.group)
            self.fqdn = self.hostname + '.' + self.domain

    def get_domain(self, group):
        domain = "%s.%s" % (group, Config["domain"])
        return domain

    def __repr__(self):
        return self.output(delim=' ')

    def __str__(self):
        return self.output(delim='\t')

    def output(self, delim='\n', printmac=False):
        infos = [
            ("Hostname: ", self.hostname),
            ("IP: ", self.ip),
        ]
        if printmac:
            infos.append(("MAC: ", self.mac))

        out = []
        for a, b in infos:
            if b:
                out += [a + str(b)]
            else:
                out += [a + '(empty)']
        return delim.join(out)

    def check_input_format(self, checkmac=True):
        num = '(2[0-5]|1[0-9]|[0-9])?[0-9]'
        ipregexp = r'('+num+'\.){3}('+num+')'
        macregexp = r'([0-9A-F]{2}:){5}([0-9A-F]{2})'
        # one could maybe also allow '-' instead of ':' here

        checks = [(self.ip, ipregexp, 'IP')]
        if checkmac:
            checks.append((self.mac, macregexp, 'MAC'))

        # run through all checks listed above
        for value, reg, name in checks:
            if not value:
                logging.debug('%s has no %s entry' % (self.hostname, name))
                continue

            res = re.search(reg, value, re.I)
            if not res:
                logging.error("the given %s is not valid for:" % name)
                logging.error(str(self))
                raise Exception("invalid input")

    @property
    def aliases(self):
        if self.prefix[0:3] in Config['groups']:
            return [self.fqdn, self.prefix, self.prefix[3:]]
        else:
            return [self.fqdn, self.prefix]

    @property
    def grsource(self):
        return self.group + self.source

    @property
    def dhcp(self):
        if self.mac and self.ip:
            # curly brackets doubled for python format funciton
            return """host {fqdn} {{
        hardware ethernet {mac};
        fixed-address {ip};
        option host-name "{hostname}";
        option domain-name "{domain}";
        }}""".format(fqdn=self.fqdn, mac=self.mac, ip=self.ip, hostname=self.hostname, domain=self.domain)

    @property
    def ansible(self):
        hostgroups = [self.group, self.source, self.grsource]
        result = {
            'hostname': self.fqdn,
            'groups': hostgroups,
            'vars':
            {
                'institute': self.group,
                'hosttype': self.source,
            }
        }
        if self.ip:
            result['vars']['ip'] = self.ip
        result['vars'].update(self.ansiblevars)
        return result

    @property
    def host(self):
        if self.ip:
            return self.ip + " " + " ".join(self.aliases)

