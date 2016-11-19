#!/usr/bin/env python3

import logging
import types
from .config import CONFIGINSTANCE as Config


class CNamelist(list):
    "Representation of the list of CNames"

    def __str__(self):
        return '\n'.join([str(h) for h in self])

    def diff(self, othercnames):
        diff = types.SimpleNamespace()
        diff.add, diff.remove = [], []

        fqdns = {h.fqdn: h for h in self}
        otherfqdns = {h.fqdn: h for h in othercnames}

        for cname in self:
            if cname.fqdn not in otherfqdns or otherfqdns[cname.fqdn].dest != cname.dest:
                diff.add.append(cname)
        for cname in othercnames:
            if cname.fqdn not in fqdns or fqdns[cname.fqdn].dest != cname.dest:
                diff.remove.append(cname)

        diff.empty = (not diff.add) and (not diff.remove)
        return diff


class FileCNamelist(CNamelist):
    "File based CNamelist"

    def __init__(self):
        source = 'cnames'  # TODO: move to config
        fname = Config["hostlistdir"] + source
        try:
            infile = open(fname)
        except:
            logging.error('file missing %s' % fname)
            return
        content = infile.readlines()
        for line in content:
            try:
                uncommented = line.split('#', 1)[0]
                parseline = uncommented.strip()
                if not parseline:
                    # line is empty (up to a comment), don't parse
                    continue
                else:
                    self.append(CNameConfline(parseline))
            except Exception as e:
                logging.error("Failed to parse host (%s) in %s." %
                              (line.strip(), infile.name))
                logging.error(e)
                raise


class DNSVSCNamelist(CNamelist):
    "DNSVS based CNamelist"

    def __init__(self, con):
        "expects a dnsvs interface passed as con"
        cnames = con.get_cnames()
        for fqdn, dest in cnames.items():
            self.append(CName(fqdn, dest))


class CName:
    def __init__(self, fqdn, dest):
        if not fqdn or not dest:
            raise Exception("wrong initialization of CName, "
                            "need both fqdn and dest")
        self.fqdn = fqdn
        self.dest = dest

    def __repr__(self):
        return 'CNAME: %s -> %s' % (self.fqdn, self.dest)


class CNameConfline(CName):
    def __init__(self, line):
        assert line.startswith('cname=')
        rhs = line.split('=')[1]
        hostnames = rhs.split(',')
        if len(hostnames) != 2:
            raise Exception('Cnames config line has the wrong format.')
        self.fqdn = hostnames[0].strip()
        self.dest = hostnames[1].strip()
