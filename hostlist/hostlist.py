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
try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    from yaml import SafeLoader

from . import host
from .config import CONFIGINSTANCE as Config


class Hostlist(list):

    def __init__(self):
        super().__init__()

    def __str__(self):
        return '\n'.join([str(h) for h in self])

    def check_consistency(self, cnames):
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
        tocheck_props = ['ip', 'mac', 'hostname']
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

    def check_missing_mac_ip(self):
        """check if hosts are missing an ip or mac"""

        success = True
        for h in self:
            if 'needs_ip' in h.vars and h.vars['needs_ip'] and h.ip is None:
                logging.error("Missing IP in %s " % h)
                success = False

        if isinstance(self, YMLHostlist):
            for h in self:
                if h.vars['needs_mac'] and h.mac is None:
                    logging.error("Missing MAC in %s " % h)
                    success = False
        return success

    def diff(self, otherhostlist):
        diff = types.SimpleNamespace()
        diff.add, diff.remove = [], []
        hostnames = {h.fqdn: h.ip for h in self if h.publicip}
        inversehostlist = {h.fqdn: h for h in self}

        otherhostnames = {h.fqdn: h.ip for h in otherhostlist if h.publicip}
        inverseotherhostlist = {h.fqdn: h for h in otherhostlist}

        for fqdn, ip in hostnames.items():
            if otherhostnames.get(fqdn) != ip:
                diff.add.append(inversehostlist[fqdn])
        for fqdn, ip in otherhostnames.items():
            if hostnames.get(fqdn) != ip:
                diff.remove.append(inverseotherhostlist[fqdn])

        diff.empty = (not diff.add) and (not diff.remove)
        return diff


class DNSVSHostlist(Hostlist):
    "Hostlist filed from DNSVS"

    def __init__(self, con):
        super().__init__()
        hosts = con.get_hosts()
        for hostname, data in hosts.items():
            ip, is_nonunique = data
            self.append(host.Host(hostname, ip, is_nonunique))


class YMLHostlist(Hostlist):
    "Hostlist filed from yml file"

    def __init__(self):
        super().__init__()
        self.fileheaders = {}
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
        for h in self:
            if 'docker' in h.vars and 'ports' in h.vars['docker']:
                # prefix docker ports with container IP
                h.vars['docker']['ports'] = [
                    str(h.ip) + ':' + port for port in h.vars['docker']['ports']
                ]

    def print(self, filter):
        filtered = [h for h in self if h.filter(filter)]
        for h in filtered:
            if logging.getLogger().level == logging.DEBUG:
                print(h.output(printgroups=True, printallvars=True))
            elif logging.getLogger().level == logging.INFO:
                print(h.output(delim='\t', printgroups=True))
            else:
                print(h.hostname)

    def check_iprange_overlap(self):
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
            if ('iprange_allow_overlap' in headera and headera['iprange_allow_overlap']) or \
               ('iprange_allow_overlap' in headerb and headerb['iprange_allow_overlap']):
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
