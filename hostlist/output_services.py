#!/usr/bin/env python3

from collections import defaultdict
import os

from .host import Host
from .hostlist import Hostlist
from .cnamelist import CNamelist
from .config import CONFIGINSTANCE as Config


class Ssh_Known_HostsOutput:
    "Generate hostlist for ssh-keyscan"

    @classmethod
    def gen_content(cls, hostlist: Hostlist, cnames: CNamelist) -> str:
        # only scan keys on hosts that are in ansible
        scan_hosts = [
            h for h in hostlist
            if h.vars.get('gen_ssh_known_hosts', False) or
            'ssh_known_hosts' in h.groups
        ]
        aliases = [alias
                   for host in scan_hosts
                   for alias in host.aliases
                   if host.ip]
        aliases += [str(host.ip)
                    for host in scan_hosts
                    if host.ip]
        aliases += [cname.fqdn for cname in cnames]

        fcont = '\n'.join(aliases)

        return fcont


class HostsOutput:
    "Config output for /etc/hosts format"

    @classmethod
    def gen_content(cls, hostlist: Hostlist, cnames: CNamelist) -> str:
        hoststrings = (str(h.ip) + " " + " ".join(h.aliases) for h in hostlist if h.ip)
        content = '\n'.join(hoststrings)
        return content


class MuninOutput:
    "Config output for Munin"

    @classmethod
    def gen_content(cls, hostlist: Hostlist, cnames: CNamelist) -> str:
        hostnames = (
            h for h in hostlist
            if h.vars.get('gen_munin', False) or
            'muninnode' in h.groups
        )
        fcont = ''
        for host in hostnames:
            fcont += cls._get_hostblock(host)
        return fcont

    @staticmethod
    def _get_hostblock(host: Host) -> str:
        cont = '[{institute}{hosttype};{h}]\naddress {h}\n'.format(
            h=host.fqdn,
            institute=host.vars['institute'],
            hosttype=host.vars['hosttype'],
        )
        for line in host.vars.get('munin', []):
            cont += line + '\n'
        return cont


class DhcpOutput:
    "DHCP config output"

    @classmethod
    def gen_content(cls, hostlist: Hostlist, cnames: CNamelist) -> str:
        out = ""
        for host in hostlist:
            entry = cls._gen_hostline(host)
            if not entry:
                continue
            out += entry + '\n'
        return out

    @staticmethod
    def _gen_hostline(host: Host) -> str:
        if host.mac and host.ip:
            # curly brackets doubled for python format function
            return """host {fqdn} {{
        hardware ethernet {mac};
        fixed-address {ip};
        option host-name "{hostname}";
        option domain-name "{domain}";
        }}""".format(fqdn=host.fqdn, mac=host.mac, ip=host.ip, hostname=host.hostname, domain=host.domain)


class AnsibleOutput:
    "Ansible inventory output"

    @classmethod
    def gen_content(cls, hostlist: Hostlist, cnames: CNamelist) -> dict:
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
        resultdict = defaultdict(lambda: {'hosts': []})  # type: dict
        #  with python>=3.6 # type: defaultdict[str, Any]
        hostvars = {}
        docker_services = {}
        for host in hostlist:
            # online add hosts that have ansible=yes
            if 'ansible' not in host.groups and ('ansible' in host.vars and not host.vars['ansible']):
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

        resultdict['_meta'] = {'hostvars': hostvars}
        if docker_services:
            resultdict['vserverhost']['vars'] = {'docker_services': docker_services}

        return resultdict

    @staticmethod
    def _gen_host_content(host):
        "Generate output for one host"

        result = {
            'fqdn': host.fqdn,
            'groups': host.groups,
            'vars': {},
        }
        if host.ip:
            result['vars']['ip'] = str(host.ip)

        ansiblevars = Config.get('ansiblevars', []) + ['hosttype', 'institute', 'docker']
        for avar in ansiblevars:
            if avar in host.vars:
                result['vars'][avar] = host.vars[avar]
        return result


class EthersOutput:
    "/etc/ethers format output"

    @classmethod
    def gen_content(cls, hostlist: Hostlist, cnames: CNamelist) -> str:
        entries = (
            "%s %s" % (h.mac, alias)
            for h in hostlist
            for alias in h.aliases
            if h.mac
        )
        out = '\n'.join(entries)
        return out


class WebOutput:
    "HTML Table of hosts"

    @classmethod
    def gen_content(cls, hostlist, cnames):
        if os.path.exists('header.html'):
            with open('header.html') as file:
                header = file.read()
        else:
            header = '<html><body>'

        fields = Config.get('weboutput_columns', ['institute', 'hosttype', 'hostname'])
        thead = '<table><thead><tr><th>' + '</th><th>'.join(fields) + '</th></tr></thead>\n'
        footer = '</table></body></html>'
        hostlist = '\n'.join(
            '<tr><td>' + '</td><td>'.join(str(h.vars.get(field, '')) for field in fields) + '</td></tr>'
            for h in hostlist
        )
        return header + thead + hostlist + footer
