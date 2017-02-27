#!/usr/bin/env python3

import ipaddress
import logging
import subprocess
import datetime
import re
from typing import Optional, List, Iterable

from .config import CONFIGINSTANCE as Config


class Host:
    """
    Representation of one host with several properties
    """

    def __init__(self, inputhostname: str, ip: str="", ipv6: str="", is_nonunique: bool=False) -> None:
        self._set_defaults()
        if ip:
            self.ip = ipaddress.ip_address(ip)
        else:
            logging.warning('host without ipv4: ' + inputhostname)
        if ipv6:
            self.ipv6 = ipaddress.ip_address(ipv6)
        self.vars['unique'] = not is_nonunique
        self._set_fqdn(inputhostname)
        self._set_publicip()

    def _set_defaults(self):
        self.vars = {
            'unique': True,
        }  # type: Dict[str, Any]

        self.ip = None  # type: Optional[ipaddress.ip_address]
        self.mac = None
        self.hostname = ""  # type: str
        self.publicip = True  # type: bool
        self.header = None  # stores header of input file
        self.groups = set(Config.get('groups', []))  # type: set

    def _set_fqdn(self, inputhostname: str):
        if inputhostname.endswith(Config["domain"]):
            dot_parts = inputhostname.split('.')
            self.hostname = dot_parts[0]  # type: str
            self.domain = '.'.join(dot_parts[1:])  # type: str
            self.fqdn = inputhostname  # type: str
        else:
            self.hostname = inputhostname  # type: str
            self.domain = self.get_domain(self.vars['institute'])  # type: str
            self.fqdn = inputhostname + '.' + self.domain  # type: str

    def _set_publicip(self):
        if self.ip and self.ip in ipaddress.ip_network(Config["iprange"]["external"]) or \
           hasattr(self, 'ipv6'):
            self.publicip = True
        else:
            self.publicip = False
            assert self.ip is None or self.ip in ipaddress.ip_network(Config["iprange"]["internal"])

    def get_domain(self, institute):
        domain = "%s.%s" % (institute, Config["domain"])
        return domain

    def __repr__(self) -> str:
        return self.output(delim=' ')

    def __str__(self) -> str:
        return self.output(delim='\t')

    def output(self,
               delim: str='\n',
               printmac: bool=False,
               printgroups: bool=False,
               printallvars: bool=False,
               printvars: Iterable=[]) -> str:

        infos = [
            ("Hostname: ", self.fqdn),
            ("IP: ", str(self.ip) + " (nonunique)" if not self.vars['unique'] else self.ip),
        ]
        if hasattr(self, 'ipv6'):
            infos.append(("IPv6: ", self.ipv6))
        if printmac:
            infos.append(("MAC: ", self.mac))

        if printallvars:
            printvars = self.vars.keys()
        for var in sorted(printvars):
            infos.append((var + ': ', self.vars.get(var)))

        if printgroups:
            infos.append(('Groups: ', ', '.join(self.groups)))

        out = []  # type: list
        for a, b in infos:
            if b:
                out += [a + str(b)]
            else:
                out += [a + '(empty)']
        return delim.join(out)

    @property
    def aliases(self) -> List[str]:
        "Generate hostname aliases for DNS"
        if self.hostname.startswith(self.vars['institute']):
            return [self.fqdn, self.hostname, self.hostname[len(self.vars['institute']):]]
        else:
            return [self.fqdn, self.hostname]


class YMLHost(Host):
    "Host generated from yml file entry"

    _num = '(2[0-5]|1[0-9]|[0-9])?[0-9]'
    IPREGEXP = re.compile(r'^(' + _num + r'\.){3}(' + _num + ')$')
    MACREGEXP = re.compile(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$')

    def __init__(self,
                 inputdata: dict,
                 hosttype: str,
                 institute: str,
                 header: Optional[dict]=None
                 ) -> None:
        """
        parses a config file line of the form
        #host=host1.abc.kit.edu        hwadress=00:12:34:ab:cd:ef      ipadress=127.0.0.1
        """
        self._set_defaults()
        self.vars['hosttype'] = hosttype
        self.vars['institute'] = institute

        if header:
            for var, value in header.items():
                self.vars[var] = value
            self.groups.update(header.get('groups', {}))
            self.groups.difference_update(header.get('notgroups', {}))

        for var, value in inputdata.items():
            self.vars[var] = value
        self.groups.update(inputdata.get('groups', {}))
        self.groups.difference_update(inputdata.get('notgroups', {}))

        if 'hostname' not in self.vars:
            raise Exception("Entry without hostname.")
        self._set_fqdn(self.vars['hostname'])

        if not self.vars['institute']:
            raise Exception("No institute given for %s." % self.vars['hostname'])
        self.groups.update({
            self.vars['hosttype'],
            self.vars['institute'],
            self.vars['institute'] + self.vars['hosttype']
        })

        self._check_macip()
        self._set_publicip()

        if header and 'iprange' in header:
            self._check_iprange(header['iprange'])
        self.header = header
        logging.debug("Added " + str(self))

    def _check_macip(self) -> None:
        "Check validity of vars set for host."
        try:
            assert self.IPREGEXP.match(self.vars['ip'])
            self.ip = ipaddress.IPv4Address(self.vars['ip'])
        except:
            raise Exception("Host %s does not have a valid IP address (%s)." % (self.fqdn, self.vars['ip']))
        try:
            if 'ipv6' in self.vars:
                self.ipv6 = ipaddress.IPv6Address(self.vars['ipv6'])
            elif 'ipv6' in self.groups:
                self.ipv6 = ipaddress.IPv6Address(Config['ipv6_prefix'] + self.vars['ip'])
        except:
            raise Exception("Host %s does not have a valid IPv6 address (%s)." % (self.fqdn, self.vars['ipv6']))
        if 'mac' in self.vars:
            try:
                assert self.MACREGEXP.match(self.vars['mac'])
                self.mac = MAC(self.vars['mac'])
            except:
                raise Exception("Host %s does not have a valid MAC address (%s)." % (self.fqdn, self.mac))

    def _check_iprange(self, iprange):
        "Check whether the given IP is in the range defined at the file header."
        if iprange is None:
            return
        assert len(iprange) == 2
        if self.ip < iprange[0] or self.ip > iprange[1]:
            raise Exception("%s has IP %s outside of range %s-%s." %
                            (self.fqdn, self.ip, iprange[0], iprange[1]))

    def run_checks(self) -> bool:
        checks = [
            self._check_user(),
            self._check_end_date(),
        ]
        return all(checks)

    def _check_end_date(self):
        "Check that end_date is not over yet"
        if 'end_date' in self.vars:
            end_date = self.vars['end_date']
            if not isinstance(end_date, datetime.date):
                logging.error("Parsing of end_date %s led to non-date datatype %s for host %s." % (end_date, end_date.__class__, self.fqdn))
                return False
            if end_date < datetime.date.today():
                logging.error("Host end_date in the past for host %s." % self.fqdn)
                return False
        return True

    def _check_user(self) -> bool:
        "Check that user (still) exists if set"
        if 'user' in self.vars:
            try:
                subprocess.check_output(['id', self.vars['user']])
            except subprocess.CalledProcessError:
                logging.error("User %s does not exist and is listed for host %s." % (self.vars['user'], self.fqdn))
                # return False
        return True

    def select(self, selectors: list) -> bool:
        "return whether the host matches the given list of selectors"
        return bool(set(selectors) & set.union(set(self.groups), set(self.aliases)))


class MAC(str):
    """Representation of a MAC address

    Based on string, but always lowercase and replacing '-' with ':'.
    """
    def __new__(cls, value):
        return super().__new__(cls, value.lower().replace('-', ':'))
