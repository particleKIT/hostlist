#!/usr/bin/env python3

from collections import defaultdict
import json
import ipaddress
import os
import logging

from .config import CONFIGINSTANCE as Config


class OutputBase:
    "Baseclass for output services"

    @classmethod
    def gen_content(cls, hostlist, cnames, stdout):
        "Return output for requested service"
        pass

    @staticmethod
    def write(content, buildname, stdout=False):
        "Write content to a file or stdout"
        if stdout:
            print(content)
        else:
            builddir = Config["builddir"]
            if not os.path.isdir(builddir):
                os.mkdir(builddir)
            fname = builddir + buildname
            with open(fname, 'w') as f:
                f.write(content)


class Ssh_Known_HostsOutput(OutputBase):
    "Generate hostlist for ssh-keyscan"

    @classmethod
    def gen_content(cls, hostlist, cnames, stdout):
        # only scan keys on hosts that are in ansible
        scan_hosts = [h for h in hostlist if h.vars.get('gen_ssh_known_hosts', False)]
        aliases = [alias
                   for host in scan_hosts
                   for alias in host.aliases
                   if host.ip]
        aliases += [str(host.ip)
                    for host in scan_hosts
                    if host.ip]
        aliases += [cname.fqdn for cname in cnames]

        fcont = '\n'.join(aliases)

        cls.write(fcont, Config["ssh"]["hostlist"], stdout)
        logging.debug("wrote ssh hostlist to file")


class HostsOutput(OutputBase):
    "Config output for /etc/hosts format"

    @classmethod
    def gen_content(cls, hostlist, cnames, stdout):
        hoststrings = (str(h.ip) + " " + " ".join(h.aliases) for h in hostlist if h.ip)
        content = '\n'.join(hoststrings)
        cls.write(content, Config["hosts"]["build"], stdout)


class MuninOutput(OutputBase):
    "Config output for Munin"

    @classmethod
    def gen_content(cls, hostlist, cnames, stdout):
        hostnames = (h for h in hostlist if h.vars.get('gen_munin', False) and h.publicip)
        fcont = ''
        for host in hostnames:
            fcont += cls._get_hostblock(host)
        cls.write(fcont, Config["munin"]["build"], stdout)

    @staticmethod
    def _get_hostblock(host):
        cont = '[{institute}{hosttype};{h}]\naddress {h}\n'.format(
            h=host.fqdn,
            institute=host.vars['institute'],
            hosttype=host.vars['hosttype'],
        )
        if 'munin' in host.vars:
            for line in host.vars['munin']:
                cont += line + '\n'
        return cont


class DhcpOutput(OutputBase):
    "DHCP config output"

    @classmethod
    def gen_content(cls, hostlist, cnames, stdout):
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
        cls.write(dhcpout, Config["dhcp"]["build"], stdout)
        cls.write(dhcp_internal, Config["dhcp"]["build_internal"], stdout)

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
    def gen_content(cls, hostlist, cnames, stdout):
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
        assert stdout, "Ansible Output only works for stdout"
        resultdict = defaultdict(lambda: {'hosts': []})
        hostvars = {}
        docker_services = {}
        for host in hostlist:
            # online add hosts that have ansible=yes
            if 'ansible' in host.vars and not host.vars['ansible']:
                continue
            ans = cls._gen_host_content(host)
            hostvars[ans['fqdn']] = ans['vars']
            for groupname in ans['groups']:
                resultdict[groupname]['hosts'] += [ans['fqdn']]

            if ans['vars']['hosttype'] == 'docker':
                resultdict['dockerhost-' + host.hostname]['hosts'] += [ans['vars']['docker']['host']]
                docker_services[host.hostname] = ans['vars']['docker']
                docker_services[host.hostname]['fqdn'] = host.fqdn
                docker_services[host.hostname]['ip'] = str(host.ip)

        resultdict['vserverhost']['vars'] = {'docker_services': docker_services}
        resultdict['_meta'] = {'hostvars': hostvars}

        jsonout = json.dumps(resultdict, sort_keys=True, indent=1)
        cls.write(jsonout, None, stdout=True)

    @staticmethod
    def _gen_host_content(host):
        "Generate output for one host"
        hostgroups = [host.vars['institute'], host.vars['hosttype'], host.vars['institute'] + host.vars['hosttype']]

        result = {
            'fqdn': host.fqdn,
            'groups': hostgroups,
            'vars': {},
        }
        if host.ip:
            result['vars']['ip'] = str(host.ip)

        ansiblevars = ['subnet', 'institute', 'hosttype', 'docker']
        for avar in ansiblevars:
            if avar in host.vars:
                result['vars'][avar] = host.vars[avar]
        return result


class EthersOutput(OutputBase):
    "/etc/ethers format output"

    @classmethod
    def gen_content(cls, hostlist, cnames, stdout):
        entries = (
            "%s %s" % (host.mac, host.fqdn) for host in hostlist
            if host.mac
        )
        out = '\n'.join(entries)
        cls.write(out, Config["ethers"], stdout)
