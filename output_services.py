#!/usr/bin/env python3

from collections import defaultdict
import json
from abc import ABCMeta, abstractmethod
import ipaddress
import os
import logging
import tempfile
import subprocess

from config import CONFIGINSTANCE as Config


class OutputBase(metaclass=ABCMeta):
    "Baseclass for output services"

    @classmethod
    @abstractmethod
    def gen_content(cls, hostlist):
        "Return output for requested service"
        pass

    @staticmethod
    def write(content, buildname):
        "Write content to a file"
        builddir = Config["builddir"]
        if not os.path.isdir(builddir):
            os.mkdir(builddir)
        fname = builddir + buildname
        with open(fname, 'w') as f:
            f.write(content)


class Ssh_Known_HostsOutput(OutputBase):
    "Generate ssh_known_hosts file"

    @classmethod
    def gen_content(cls, hostlist):
        # only scan keys on hosts that are in ansible
        scan_hosts = [h for h in hostlist if h.vars.get('gen_ssh_known_hosts', False)]
        aliases = [a.encode()
                   for host in scan_hosts
                   for a in host.aliases
                   if host.ip]
        aliases += [str(host.ip).encode()
                    for host in scan_hosts
                    if host.ip]

        with tempfile.NamedTemporaryFile() as f:
            f.file.write(b"\n".join(aliases))
            f.file.flush()
            call = ['ssh-keyscan', '-T', '1', '-t', 'ed25519', '-f', f.name]
            p = subprocess.Popen(call,
                                 stderr=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE,
                                 bufsize=-1)
            logging.info("started ssh session")
            out, err = p.communicate()
            logging.info("communicated with hosts")

        newhosts = cls._ssh_keyscan_to_hash(out.decode())
        oldout = ""
        with open(Config["ssh"]["import"]) as previousf:
            oldout = previousf.read()
        hosts = cls._ssh_keyscan_to_hash(oldout)
        hosts.update(newhosts)

        hosts = cls._combine_ssh_hosts(hosts)
        sorted_hosts = sorted(hosts)

        fcont = '\n'.join(
            [hname + ' ' + hosts[hname] for hname in sorted_hosts]
        )
        # ssh_known_hosts needs trailing newline
        # otherwise ssh-keygen will complain when reading it
        fcont += '\n'

        cls.write(fcont, Config["ssh"]["build"])
        logging.debug("wrote ssh hostkeys to file")


    @staticmethod
    def _ssh_keyscan_to_hash(indata):
        "Convert keyscan results to python dict of hostkeys"
        hosts = {}
        for l in indata.splitlines():
            fields = l.split()
            if fields == []:
                continue
            if len(fields) < 3:
                logging.warning("encountered too short line: " + str(l))
                continue
            hnames = fields[0]
            keytype = fields[1]
            key = fields[2]
            for host in hnames.split(','):
                # prefer ed25519 over everything else
                if host in hosts and \
                   keytype != 'ed25519' and \
                   hosts[host].startswith('ed25519'):
                        pass
                else:
                    hosts[host] = keytype + ' ' + key
        return hosts

    @staticmethod
    def _combine_ssh_hosts(hosts):
        """make the given dict host->sshkey shorter, by combinding hostnames
        with the same key"""
        # keymap: {'ed25519 key':['host1', 'host2']}
        keymap = defaultdict(list)
        for host, key in hosts.items():
            keymap[key].append(host)
        # shorthosts: { 'pcXX,abcpcXX,...':'ed25519 ...'}
        # sorted makes them more readable, set ensured there are no duplicates
        shorthosts = {','.join(sorted(set(hosts))): key for key, hosts in keymap.items()}
        return shorthosts


class HostsOutput(OutputBase):
    "Config output for /etc/hosts format"

    @classmethod
    def gen_content(cls, hostlist):
        hoststrings = (str(h.ip) + " " + " ".join(h.aliases) for h in hostlist if h.ip)
        content = '\n'.join(hoststrings)
        cls.write(content, Config["hosts"]["build"])


class MuninOutput(OutputBase):
    "Config output for Munin"

    @classmethod
    def gen_content(cls, hostlist):
        hostnames = [h.fqdn for h in hostlist if h.vars.get('gen_munin', False) and h.publicip]
        fcont = ''
        for host in hostnames:
            fcont += '[{h}]\naddress {h}\n'.format(h=host)
        cls.write(fcont, Config["munin"]["build"])


class DhcpOutput(OutputBase):
    "DHCP config output"

    @classmethod
    def gen_content(cls, hostlist):
        dhcpout = ""
        dhcp_internal = ""
        for host in hostlist:
            entry = cls._gen_hostline(host)
            if not entry:
                continue
            if host.ip in ipaddress.ip_network(Config['iprange']['internal']):
                dhcp_internal += entry + '\n'
            else:
                dhcpout += entry + '\n'
        cls.write(dhcpout, Config["dhcp"]["build"])
        cls.write(dhcp_internal, Config["dhcp"]["build_internal"])

    @staticmethod
    def _gen_hostline(host):
        if host.mac and host.ip:
            # curly brackets doubled for python format funciton
            return """host {fqdn} {{
        hardware ethernet {mac};
        fixed-address {ip};
        option host-name "{hostname}";
        option domain-name "{domain}";
        }}""".format(fqdn=host.fqdn, mac=host.mac, ip=host.ip, hostname=host.hostname, domain=host.domain)




class AnsibleOutput(OutputBase):
    "Ansible inventory output"

    @classmethod
    def gen_content(cls, hostlist):
        """generate json inventory for ansible
        form:
            {
        "_meta": {
            "hostvars": {
                "myhost.abc.kit.edu": {
                    "hosttype": "desktop",
                    "institute": "abc",
                    "custom_variable": "foo",
                }
                ...
                }
             },
          "groupname" : [
              "myhost2.abc.kit.edu",
          ]
            ...

        """
        resultdict = defaultdict(list)
        hostvars = {}
        for host in hostlist:
            # online add hosts that have ansible=yes
            if 'ansible' in host.vars and not host.vars['ansible']:
                continue
            ans = cls._gen_host_content(host)
            hostvars[ans['hostname']] = ans['vars']
            for groupname in ans['groups']:
                resultdict[groupname] += [ans['hostname']]

        resultdict['_meta'] = {'hostvars': hostvars}

        jsonout = json.dumps(resultdict, sort_keys=True, indent=4)
        return jsonout

    @staticmethod
    def _gen_host_content(host):
        "Generate output for one host"
        hostgroups = [host.vars['institute'], host.vars['hosttype'], host.vars['institute'] + host.vars['hosttype']]
        result = {
            'hostname': host.fqdn,
            'groups': hostgroups,
            'vars': {},
        }
        if host.ip:
            result['vars']['ip'] = str(host.ip)

        ansiblevars = ['subnet', 'institute', 'hosttype']
        for avar in ansiblevars:
            if avar in host.vars:
                result['vars'][avar] = host.vars[avar]
        return result
