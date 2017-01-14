#!/usr/bin/env python3

import logging
from types import SimpleNamespace
from typing import Dict

from .config import CONFIGINSTANCE as Config


class CNamelist(list):
    "Representation of the list of CNames"

    def __str__(self) -> str:
        return '\n'.join([str(h) for h in self])

    def diff(self, othercnames: list) -> SimpleNamespace:
        diff = SimpleNamespace()
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

    def __init__(self) -> None:
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
                logging.error(str(e))
                raise


class DNSVSCNamelist(CNamelist):
    "DNSVS based CNamelist"

    def __init__(self, cnames: Dict[str, str]) -> None:
        "expects a dnsvs interface passed as con"
        for fqdn, dest in cnames.items():
            self.append(CName(fqdn, dest))


class CName:
    def __init__(self, fqdn: str, dest: str) -> None:
        self.fqdn = fqdn
        self.dest = dest

    def __repr__(self) -> str:
        return 'CNAME: %s -> %s' % (self.fqdn, self.dest)


class CNameConfline(CName):
    def __init__(self, line: str) -> None:
        assert line.startswith('cname=')
        rhs = line.split('=')[1]
        hostnames = rhs.split(',')
        if len(hostnames) != 2:
            raise Exception('Cnames config line has the wrong format.')
        self.fqdn = hostnames[0].strip()
        self.dest = hostnames[1].strip()
