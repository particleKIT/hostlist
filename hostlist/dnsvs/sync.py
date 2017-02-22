#!/usr/bin/env python3

import logging
from types import SimpleNamespace
from collections import namedtuple

from . import DNSVSInterface

# use termcolor when available, otherwise ignore
try:
    from termcolor import colored
except ImportError:
    def colored(text, _):
        return text


DiffStep = namedtuple('Diffstep', ('list', 'function', 'label'))


def apply_diff(host_diff: SimpleNamespace, cname_diff: SimpleNamespace):
    con = DNSVSInterface()
    steps = [
        DiffStep(cname_diff.remove, con.remove_cname, 'removing cname'),
        DiffStep(host_diff.remove, con.remove_host, 'removing host'),
        DiffStep(host_diff.removev6, con.remove_hostv6, 'removing host'),
        DiffStep(host_diff.add, con.add_host, 'adding host'),
        DiffStep(host_diff.addv6, con.add_hostv6, 'adding host'),
        DiffStep(cname_diff.add, con.add_cname, 'adding cname'),
    ]
    for step in steps:
        for entry in step.list:
            logging.info(step.label + '\t' + str(entry))
            step.function(entry)


def print_diff(host_diff: SimpleNamespace, cname_diff: SimpleNamespace) -> None:
    for section, label, color, sign in [
        (host_diff.add, 'local files', 'green', '+'),
        (host_diff.addv6, 'local files (v6)', 'green', '+'),
        (cname_diff.add, 'local files', 'green', '+'),
        (host_diff.remove, 'DNSVS', 'red', '-'),
        (host_diff.removev6, 'DNSVS (v6)', 'red', '-'),
        (cname_diff.remove, 'DNSVS (v6)', 'red', '-'),
    ]:
        if section:
            print(colored("Only in " + label + ": ", color))
            for h in sorted(section, key=lambda h: h.fqdn):
                print(colored(sign + str(h), color))
