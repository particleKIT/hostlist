#!/usr/bin/env python3

import logging

from . import dnsvs_webapi as dnsvs
from ..cnamelist import CName
from ..host import Host

# use termcolor when available, otherwise ignore
try:
    from termcolor import colored
except ImportError:
    def colored(text, _):
        return text


def apply_diff(diff):
    con = dnsvs.dnsvs_interface()
    removelist = \
        list(filter(lambda h: isinstance(h, CName), diff.remove)) + \
        list(filter(lambda h: isinstance(h, Host), diff.remove))
    addlist = \
        list(filter(lambda h: isinstance(h, Host), diff.add)) + \
        list(filter(lambda h: isinstance(h, CName), diff.add))
    for entry in removelist:
        logging.info('removing\t' + str(entry))
        con.remove(entry)
    for entry in addlist:
        logging.info('adding\t' + str(entry))
        con.add(entry)


def print_diff(diff):
    if diff.add:
        print(colored("Only in local files: ", 'green'))
        for h in sorted(diff.add, key=lambda h: h.fqdn):
            print(colored('+' + str(h), 'green'))
    if diff.remove:
        print(colored("Only in DNSVS: ", 'red'))
        for h in sorted(diff.remove, key=lambda h: h.fqdn):
            print(colored('-' + str(h), 'red'))
