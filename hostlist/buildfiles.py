#!/usr/bin/env python3
# pylint: disable=broad-except

import argparse
import logging
import subprocess
import types
from distutils.util import strtobool
import sys

from hostlist import hostlist
from hostlist import cnamelist
from hostlist import output_services
from hostlist.config import CONFIGINSTANCE as Config
try:
    from hostlist.dnsvs import sync
    from hostlist.dnsvs import dnsvs_webapi as dnsvs
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
                        help='only create build files, but don\'t deploy')

    parser.add_argument('--stdout',
                        action='store_true',
                        help='Output to stdout instead of writing to a file.'
                        ' Only implemented for ssh_known_hosts so far.')

    parser.add_argument('--dnsvs',
                        action='store_true',
                        help='sync with dnsvs')

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


def run_deploy():
    "Deploy DNS/DHCP settings to servers"

    deployhosts = Config['deployhosts']
    for host in deployhosts:
        print("Do you want to deploy to %s? (y/n)" % host)
        choice = input().lower()
        if choice != '' and strtobool(choice):
            print("Please enter deploy password:")
            ssh_res = subprocess.check_call([
                'ssh', "root@%s" % host,
                '-o', 'ControlPath=~/.ssh/controlmasters-%r@%h:%p',
                '-o', 'ControlMaster=auto',
                'echo', 'success'
            ])
            if ssh_res != 0:
                logging.error("Failed to establigh ssh connection to %s."
                              " Skipping deploy.", host)
                continue
            print("Running in checkmode with diff first.")
            try:
                stdout = subprocess.check_output([
                    "ansible-playbook",
                    '--check',
                    '--diff',
                    "copy_dns_dhcp_to_server.yml",
                    "-l",
                    host])
            except subprocess.CalledProcessError:
                logging.error("Ansible check failed, skipping deploy.")
                continue
            print(stdout.decode())
            print("Do you really want to deploy to %s? (y/n)" % host)
            choice = input().lower()
            if choice != '' and strtobool(choice):
                subprocess.call(["ansible-playbook",
                                 "copy_dns_dhcp_to_server.yml",
                                 "-l",
                                 host])


def run_servies(args, servicedict, file_hostlist, file_cnames):
    "Run all services according to servicedict on hosts in file_hostlist."
    for service, start in servicedict.items():
        if start:
            outputcls = getattr(output_services, service.title() + "Output", None)
            if outputcls:
                logging.info("generating output for " + service)
                outputcls.gen_content(file_hostlist, file_cnames, args.stdout)
            else:
                logging.error("missing make function for " + service)


def main():
    "main routine"

    logging.basicConfig(format='%(levelname)s:%(message)s')

    services = ['dhcp', 'hosts', 'munin', 'ssh_known_hosts', 'ansible', 'ethers']
    args = parse_args(services)

    if args.stdout:
        args.quiet = True
        args.dryrun = True

    logging.getLogger().setLevel(logging.INFO)
    if args.verbose >= 1:
        logging.getLogger().setLevel(logging.DEBUG)
    if args.quiet:
        logging.getLogger().setLevel(logging.CRITICAL)

    # get a dict of the arguments
    argdict = vars(args)
    servicedict = {s: argdict[s] for s in services}

    if args.stdout and not sum(servicedict.values()) == 1:
        logging.error("For stdout output exactly one service has to be enabled.")
        sys.exit(1)

    logging.info("loading hostlist from yml files")
    file_hostlist = hostlist.YMLHostlist()
    logging.info("loading cnames from file")
    file_cnames = cnamelist.FileCNamelist()

    file_hostlist.check_consistency(file_cnames)

    rundeploy = False
    rundnsvs = False
    # run set of default operations when none specified
    if not any(servicedict.values()):
        servicedict['dhcp'] = True
        servicedict['hosts'] = True
        rundeploy = True

        # don't sync with dnsvs on dryrun
        rundnsvs = not args.dryrun

    if args.dnsvs or rundnsvs:
        sync_dnsvs(file_hostlist, file_cnames, args.dryrun)

    run_servies(args, servicedict, file_hostlist, file_cnames)

    if not args.quiet:
        subprocess.call(["git", "--no-pager", "diff", "-U0", "build"])

    if rundeploy and not args.dryrun:
        run_deploy()

    if not args.quiet:
        print('-' * 40)
        print("please remember to commit and push when you are done")
        print("git commit -av && git push")
