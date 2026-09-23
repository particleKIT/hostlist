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


def sync_ipv6(file_hostlist, con, dryrun: bool = False) -> None:
    """One-way AAAA sync: adds AAAA records for hosts carrying an 'ipv6:'
    field if (and only if) no AAAA record exists yet for that fqdn. Existing
    AAAA records are never modified or removed automatically."""
    try:
        existing = con.get_ipv6()
    except Exception as exc:
        logging.error(str(exc))
        logging.error("Failed to read AAAA records from DNSVS, skipping IPv6 sync.")
        return
    for h in file_hostlist:
        if not h.ipv6:
            continue
        fqdn = h.fqdn
        want = str(h.ipv6)
        if existing.get(fqdn) == want:
            continue
        if fqdn in existing:
            logging.warning("AAAA mismatch for %s (DNSVS: %s, local: %s) -"
                            " not touching it, fix by hand"
                            " (remove_ipv6 via dnsvs interface).", fqdn,
                            existing[fqdn], want)
            continue
        logging.info("adding AAAA record\t%s AAAA %s", fqdn, want)
        if not dryrun:
            con.add_ipv6(h)


def print_diff(diff: SimpleNamespace) -> None:
    for section, label, color, sign in [
        (diff.add, 'local files', 'green', '+'),
        (diff.remove, 'DNSVS', 'red', '-'),
    ]:
        if section:
            print(colored("Only in " + label + ": ", color))
            for h in sorted(section, key=lambda h: h.fqdn):
                print(colored(sign + str(h), color))
