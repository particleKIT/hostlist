#!/usr/bin/env python3

import logging
import types
from collections import defaultdict
import os
import sys
import ipaddress
import itertools
import glob
import yaml
from typing import Dict
try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    from yaml import SafeLoader

from . import host
from .config import CONFIGINSTANCE as Config


class Hostlist(list):

    def __init__(self):
        super().__init__()
        self.fileheaders = {}

    def __str__(self):
        return '\n'.join([str(h) for h in self])

    def diff(self, otherhostlist) -> types.SimpleNamespace:
        diff = types.SimpleNamespace()
        diff.add, diff.remove = [], []
        diff.addv6, diff.removev6 = [], []
        hostnames = {h.fqdn: h.ip for h in self if h.publicip}
        hostnamesv6 = {h.fqdn: h.ipv6 for h in self if h.publicip and hasattr(h, 'ipv6')}
        inversehostlist = {h.fqdn: h for h in self}

        otherhostnames = {h.fqdn: h.ip for h in otherhostlist if h.publicip}
        otherhostnamesv6 = {h.fqdn: h.ipv6 for h in otherhostlist if h.publicip and hasattr(h, 'ipv6')}
        inverseotherhostlist = {h.fqdn: h for h in otherhostlist}

        for fqdn, ip in hostnames.items():
            if otherhostnames.get(fqdn) != ip:
                diff.add.append(inversehostlist[fqdn])
        for fqdn, ip in otherhostnames.items():
            if hostnames.get(fqdn) != ip:
                diff.remove.append(inverseotherhostlist[fqdn])

        for fqdn, ipv6 in hostnamesv6.items():
            if otherhostnamesv6.get(fqdn) != ipv6:
                diff.addv6.append(inversehostlist[fqdn])
        for fqdn, ipv6 in otherhostnamesv6.items():
            if hostnamesv6.get(fqdn) != ipv6:
                diff.removev6.append(inverseotherhostlist[fqdn])

        diff.empty = not any((diff.add, diff.remove, diff.addv6, diff.removev6))

        return diff


class DNSVSHostlist(Hostlist):
    "Hostlist filed from DNSVS"

    def __init__(self, input: Dict[str, Dict]) -> None:
        super().__init__()
        for hostname, data in input.items():
            self.append(host.Host(hostname, **data))


class YMLHostlist(Hostlist):
    "Hostlist filed from yml file"

    def __init__(self):
        super().__init__()
        self.groups = defaultdict(list)
        input_ymls = sorted(glob.glob(Config["hostlistdir"] + '/*.yml'))
        logging.debug("Using %s" % ', '.join(input_ymls))
        for inputfile in input_ymls:
            self._add_ymlhostfile(inputfile)

    def _add_ymlhostfile(self, fname):
        "parse all hosts in fname and add them to this hostlist"

        shortname = os.path.splitext(os.path.basename(fname))[0]
        if shortname.count('-') > 1:
            logging.error('Filename %s contains to many dashes. Skipped.')
            return
        if '-' in shortname:
            # get abc, def from hostlists/abc-def.yml
            hosttype, institute = shortname.split('-')
        else:
            hosttype = shortname
            institute = None
        try:
            infile = open(fname, 'r')
        except:
            logging.error('file %s not readable' % fname)
            return

        try:
            yamlsections = yaml.load_all(infile, Loader=SafeLoader)
        except yaml.YAMLError as e:
            logging.error('file %s not correct yml' % fname)
            logging.error(str(e))
            return

        for yamlout in yamlsections:
            self._parse_section(yamlout, fname, hosttype, institute)

        self._fix_docker_ports()

    def _parse_section(self, yamlout, fname, hosttype, institute):
        for field in ('header', 'hosts'):
            if field not in yamlout:
                logging.error('missing field %s in %s' % (field, fname))

        header = yamlout['header']
        if 'iprange' in header:
            ipstart, ipend = header['iprange']
            header['iprange'] = ipaddress.ip_address(ipstart), ipaddress.ip_address(ipend)
        self.fileheaders[os.path.basename(fname)] = header

        for hostdata in yamlout["hosts"]:
            newhost = host.YMLHost(hostdata, hosttype, institute, header)
            self.append(newhost)
            for group in newhost.groups:
                self.groups[group].append(newhost)

    def _fix_docker_ports(self):
        "Add ip: prefix to port statements in docker"
        for thish in self:
            if 'docker' in thish.vars and 'ports' in thish.vars['docker']:
                # prefix docker ports with container IP
                thish.vars['docker']['ports'] = [
                    str(thish.ip) + ':' + port for port in thish.vars['docker']['ports']
                ]

    def print(self, selectors):
        "print all hosts matching the selectors"
        for thish in filter(lambda h: h.select(selectors), self):
            if logging.getLogger().level == logging.DEBUG:
                print(thish.output(printgroups=True, printallvars=True))
            elif logging.getLogger().level == logging.INFO:
                print(thish.output(delim='\t', printgroups=True))
            else:
                print(thish.hostname)

    def check_consistency(self, cnames):
        "run all consistency checks"
        checks = [
            self.check_nonunique(),
            self.check_cnames(cnames),
            self.check_duplicates(),
            self.check_missing_mac_ip(),
            all(h.run_checks() for h in self),
        ]

        if isinstance(self, YMLHostlist):
            checks.append(self.check_iprange_overlap())

        logging.info("consistency check finished")
        if not all(checks):
            sys.exit(1)

    def check_nonunique(self):
        """ensure nonunique flag agrees with nonunique_ips config"""
        success = True
        nonunique_ips = defaultdict(list)
        for h in self:
            ip_fit = str(h.ip) in Config["nonunique_ips"]
            if ip_fit and h.vars['unique']:
                nonunique_ips[str(h.ip)].append(h)
            if not ip_fit and not h.vars['unique']:
                logging.error("Host %s has nonunique ip flag, "
                              "but its ip is not listed in the config." % h)
                success = False

        for ip in nonunique_ips:
            if len(nonunique_ips[ip]) > 1:
                logging.error("More than one host uses a given nonunique ip"
                              " without being flagged:\n" +
                              ('\n'.join((str(x) for x in nonunique_ips[ip]))))
                success = False

        return success

    def check_cnames(self, cnames):
        """ensure there are no duplicates between hostlist and cnames"""
        success = True
        for cname in cnames:
            has_dest = False
            for h in self:
                if h.fqdn == cname.fqdn:
                    logging.error("%s conflicts with %s." % (cname, h))
                    success = False
                if cname.dest == h.fqdn:
                    has_dest = True
            if not has_dest:
                logging.error("%s points to a non-existing host." % cname)
                success = False
        return success

    def check_duplicates(self):
        """check consistency of hostlist

        detect duplicates (ip, mac, hostname)"""

        success = True
        inverselist = {}
        tocheck_props = ['ip', 'mac', 'fqdn']
        for prop in tocheck_props:
            inverselist[prop] = {}
            for h in self:
                myhostprop = getattr(h, prop)
                if myhostprop is None:
                    continue
                if prop == 'ip' and str(myhostprop) in Config["nonunique_ips"]:
                    # allow nonunique ips if listed in config
                    continue
                if myhostprop in inverselist[prop]:
                    logging.error("Found duplicate %s for hosts \n%s\n%s"
                                  % (prop, inverselist[prop][myhostprop], h))
                    success = False
                inverselist[prop][myhostprop] = h
        return success

    def check_missing_mac_ip(self) -> bool:
        """check if hosts are missing an ip or mac"""

        success = True
        for h in self:
            if 'needs_ip' in h.groups and h.ip is None:
                logging.error("Missing IP in %s ", h)
                success = False

        if isinstance(self, YMLHostlist):
            for h in self:
                if 'needs_mac' in h.groups and h.mac is None:
                    logging.error("Missing MAC in %s ", h)
                    success = False
        return success

    def check_iprange_overlap(self) -> bool:
        "check whether any of the ipranges given in headers overlap"

        overlaps = []
        for ita, itb in itertools.combinations(self.fileheaders.items(), 2):
            filea, headera = ita
            fileb, headerb = itb
            try:
                a = headera['iprange']
                b = headerb['iprange']
            except KeyError:
                # one of the files does not have iprange defined, ignore it
                continue
            if headera.get('iprange_allow_overlap', False) or \
               headerb.get('iprange_allow_overlap', False):
                # FIXME: check overlap for internal IPs
                continue

            # check if there is overlap between a and b
            overlap_low = max(a[0], b[0])
            overlap_high = min(a[1], b[1])
            if overlap_low <= overlap_high:
                overlaps.append((overlap_low, overlap_high, filea, fileb))
        if overlaps:
            for overlap in overlaps:
                logging.error("Found overlap from %s to %s in files %s and %s." % overlap)
        return not bool(overlaps)
