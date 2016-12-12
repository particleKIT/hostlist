#!/usr/bin/env python3
# pylint: disable=broad-except

import argparse
import logging
import types
from distutils.util import strtobool
import sys
import json

from . import hostlist
from . import cnamelist
from . import output_services
from .config import CONFIGINSTANCE as Config
try:
    from .dnsvs import sync
    from .dnsvs import dnsvs_webapi as dnsvs
    HAS_DNSVS = True
except ImportError:
    HAS_DNSVS = False


def parse_args(services):
    "setup parser for script arguments"
    parser = argparse.ArgumentParser(
        description='create all configuration files based on host input',
    )

    parser.add_argument('--verbose',
                        '-v',
                        action='count',
                        help='more output',
                        default=0)
    parser.add_argument('--quiet',
                        '-q',
                        action='store_true',
                        help='quiet run, only output errors')
    parser.add_argument('--dryrun',
                        '-d',
                        action='store_true',
                        help='only parse, don\'t sync')
    parser.add_argument('filter',
                        nargs='*',
                        help='''Print hosts matching a given filter. This can be hostnames or groupnames.''')

    for service in services:
        parser.add_argument('--' + service,
                            action='store_true',
                            help='run ' + service)

    args = parser.parse_args()
    return args


def combine_diffs(*diffs):
    """combines several diffs into one"""
    total = types.SimpleNamespace()
    total.add, total.remove = [], []
    for diff in diffs:
        total.add.extend(diff.add)
        total.remove.extend(diff.remove)
    total.empty = (not total.add) and (not total.remove)
    return total


def sync_dnsvs(file_hostlist, file_cnames, dryrun):
    "sync hostlist with dnsvs"
    if not HAS_DNSVS:
        logging.error("Import of DNSVS failed. Are all requirements installed?")
        return
    try:
        con = dnsvs.dnsvs_interface()
        logging.info("loading hostlist from dnsvs")
        dnsvs_hostlist = hostlist.DNSVSHostlist(con)
        logging.info("loading cnames from dnsvs")
        dnsvs_cnames = cnamelist.DNSVSCNamelist(con)
    except Exception as exc:
        logging.error(exc)
        logging.error("Failed to connect to DNSVS."
                      " Please make sure you have a valid ssl key,"
                      " cf. Readme.md.")
        logging.error("Not syncing with DNSVS.")
    else:
        dnsvs_hostlist.check_consistency(dnsvs_cnames)

        dnsvs_diff = file_hostlist.diff(dnsvs_hostlist)
        dnsvs_cnames_diff = file_cnames.diff(dnsvs_cnames)
        total_diff = combine_diffs(dnsvs_diff, dnsvs_cnames_diff)
        if total_diff.empty:
            logging.info("DNSVS and local files agree, nothing to do")
        else:
            sync.print_diff(total_diff)

        if not dryrun and not total_diff.empty:
            print("Do you want to apply this patch to dnsvs? (y/n)")
            choice = input().lower()
            if choice != '' and strtobool(choice):
                sync.apply_diff(total_diff)


def run_service(service, file_hostlist, file_cnames):
    "Run all services according to servicedict on hosts in file_hostlist."
    outputcls = getattr(output_services, service.title() + "Output", None)
    if outputcls:
        logging.info("generating output for " + service)
        out = outputcls.gen_content(file_hostlist, file_cnames)
        if isinstance(out, str):
            print(out)
        else:
            print(json.dumps(out, indent=2))
    else:
        logging.critical("missing make function for " + service)


def main():
    "main routine"

    logging.basicConfig(format='%(levelname)s:%(message)s')

    services = ['dhcp', 'dhcpinternal', 'hosts', 'munin', 'ssh_known_hosts', 'ansible', 'ethers']
    args = parse_args(services)

    # get a dict of the arguments
    argdict = vars(args)
    activeservices = {s for s in services if argdict[s]}

    if activeservices:
        if len(activeservices) > 1:
            logging.error("Can only output one service at a time.")
            sys.exit(2)
        args.quiet = True
        args.dryrun = True

    logging.getLogger().setLevel(logging.INFO)
    if args.verbose >= 1:
        logging.getLogger().setLevel(logging.DEBUG)
    if args.quiet:
        logging.getLogger().setLevel(logging.ERROR)

    if not Config.load():
        logging.error("Need %s file to run." % Config.CONFIGNAME)
        sys.exit(1)

    logging.info("loading hostlist from yml files")
    file_hostlist = hostlist.YMLHostlist()
    logging.info("loading cnames from file")
    file_cnames = cnamelist.FileCNamelist()

    if args.filter:
        file_hostlist.print(args.filter)
        sys.exit(0)

    if activeservices:
        run_service(activeservices.pop(), file_hostlist, file_cnames)

    if not args.dryrun:
        sync_dnsvs(file_hostlist, file_cnames, args.dryrun)

    if not args.quiet:
        print('-' * 40)
        print("please remember to commit and push when you are done")
        print("git commit -av && git push")
