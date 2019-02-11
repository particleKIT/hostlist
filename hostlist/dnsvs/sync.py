#!/usr/bin/env python3

import logging
from types import SimpleNamespace
from collections import namedtuple

from . import DNSVSInterface
from ..cnamelist import CName
from ..host import Host

# use termcolor when available, otherwise ignore
try:
    from termcolor import colored
except ImportError:
    def colored(text, _): # type: ignore
        return text


DiffStep = namedtuple('Diffstep', ('type', 'action', 'function', 'label'))


def apply_diff(diff):
    con = DNSVSInterface()
    steps = [
        DiffStep(CName, diff.remove, con.remove_cname, 'removing cname'),
        DiffStep(Host, diff.remove, con.remove_host, 'removing host'),
        DiffStep(Host, diff.add, con.add_host, 'adding host'),
        DiffStep(CName, diff.add, con.add_cname, 'adding cname'),
    ]
    for step in steps:
        sublist = list(filter(lambda x: isinstance(x, step.type), step.action))
        for entry in sublist:
            logging.info(step.label + '\t' + str(entry))
            step.function(entry)


def print_diff(diff: SimpleNamespace) -> None:
    for section, label, color, sign in [
        (diff.add, 'local files', 'green', '+'),
        (diff.remove, 'DNSVS', 'red', '-'),
    ]:
        if section:
            print(colored("Only in " + label + ": ", color))
            for h in sorted(section, key=lambda h: h.fqdn):
                print(colored(sign + str(h), color))
