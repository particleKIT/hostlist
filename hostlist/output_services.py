#!/usr/bin/env python3

from collections import defaultdict
import os
import logging
import ansiblecmdb
import ansiblecmdb.render as render
import json

from .host import Host
from .hostlist import Hostlist
from .cnamelist import CNamelist
from .config import CONFIGINSTANCE as Config

Output_Services = {} # type: dict

class Output_Register(type):
    def __new__(cls, clsname, bases, attrs):
        newcls = super(Output_Register, cls).__new__(cls, clsname, bases, attrs)
        if hasattr(newcls, 'gen_content'):
            Output_Services.update({clsname: newcls.gen_content})
        return newcls

class Output(metaclass=Output_Register):
    pass

class ssh_known_hosts(Output):
    "Generate hostlist for ssh-keyscan"

    @classmethod
    def gen_content(cls, hostlist: Hostlist, cnames: CNamelist) -> str:
        # only scan keys on hosts that are in ansible
        scan_hosts = [
            h for h in hostlist
            if 'ssh_known_hosts' in h.groups
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


class hosts(Output):
    "Config output for /etc/hosts format"

    @classmethod
    def gen_content(cls, hostlist: Hostlist, cnames: CNamelist) -> str:
        hoststrings = (str(h.ip) + " " + " ".join(h.aliases) for h in hostlist if h.ip)
        content = '\n'.join(hoststrings)
        return content


class munin(Output):
    "Config output for Munin"

    @classmethod
    def gen_content(cls, hostlist: Hostlist, cnames: CNamelist) -> str:
        hostnames = (
            h for h in hostlist
            if 'muninnode' in h.groups
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


class dhcp(Output):
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
        return ""


class ansible(Output):
    "Ansible inventory output"
    @classmethod
    def gen_content(cls, hostlist: Hostlist, cnames: CNamelist) -> str:
        return cls._gen_inventory(hostlist, cnames)

    @classmethod
    def _gen_inventory(cls, hostlist: Hostlist, cnames: CNamelist) -> str:
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
            if 'ansible' not in host.groups:
                continue
            ans = cls._gen_host_content(host)
            hostvars[ans['fqdn']] = ans['vars']
            for groupname in ans['groups']:
                resultdict[groupname]['hosts'] += [ans['fqdn']]

            if ans['vars']['hosttype'] == 'docker':
                resultdict['dockerhost_' + host.hostname]['hosts'] += [ans['vars']['docker']['host']]
                docker_services[host.hostname] = ans['vars']['docker']
                docker_services[host.hostname]['fqdn'] = host.fqdn
                docker_services[host.hostname]['ip'] = str(host.ip)

        resultdict['_meta'] = {'hostvars': hostvars}
        if docker_services:
            resultdict['vserverhost']['vars'] = {'docker_services': docker_services}

        return json.dumps(resultdict,indent=2)

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

class cmdb(ansible):
    "Use ansible-cmdb to create webpages from inventory"
    @classmethod
    def gen_content(cls, hostlist, cnames):
        conf = Config.get('ansible_cmdb', {})
        data_dir = conf.get('data_dir', '/usr/lib/ansiblecmdb/data')
        tpl_dir = os.path.join(data_dir, 'tpl')
        tpl = conf.get('template', 'html_fancy')
        cols = conf.get('columns', None)
        custom_cols = conf.get('custom_columns', [])
        cols_excl = conf.get('columns_exclude', None)
        fact_dirs = conf.get('fact_dirs', [])

        # generate ansible inventory
        json_inventory = cls._gen_inventory(hostlist,cnames)
        # use cmdb parser to parse it
        inventory_parsed = ansiblecmdb.DynInvParser(json_inventory)
        # add hosts to cmdb 'database', also load previously generated facts
        cmdb = ansiblecmdb.Ansible(fact_dirs=fact_dirs)
        for host,hostvars in inventory_parsed.hosts.items():
            cmdb.update_host(host,hostvars)
        for fact_dir in fact_dirs:
            cmdb._parse_fact_dir(fact_dir, fact_cache=True)
        # run the cmdb render
        renderer = render.Render(tpl, ['.', tpl_dir])
        params = {
            'lib_dir': data_dir,
            'data_dir': data_dir,
            'version': '',
            'log': logging.getLogger(),
            'columns': cols,
            'cust_cols': custom_cols,
            'exclude_columns': cols_excl
        }
        out = renderer.render(cmdb.hosts, params)
        return out.decode('utf8')

class ethers(Output):
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
