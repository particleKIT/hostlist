#!/usr/bin/env python3

import os.path
import logging
import subprocess
import argparse
from distutils.util import strtobool
import sys

from . import hostlist


def yes_no_query(question, empty_means=None):
    if empty_means is None:
        choices = '[y/n]'
    elif empty_means is True:
        choices = '[Y/n]'
    elif empty_means is False:
        choices = '[y/N]'
    sys.stdout.write('%s %s' % (question, choices))
    while True:
        inp = input()
        if inp.strip() == '' and empty_means is not None:
            return empty_means
        else:
            try:
                return strtobool(inp)
            except ValueError:
                print('Please respond with \'y\' or \'n\'.')


def get_next_ip(ipstart, ipend, existing_ips):
    newip = ipstart
    while newip <= ipend:
        if newip not in existing_ips:
            return newip
        newip += 1
    return None


def parse_args():
    parser = argparse.ArgumentParser(description="Add a new host to hostlist.")
    parser.add_argument('hostname', help='New hostname, e.g. fullname.itp.kit.edu, ttpmyfriend, itpalbatros98, newmachine.particle')
    parser.add_argument('hostlist', help='Filename to add to, e.g. desktops.itp.'
                        ' The prefix "hostlists/" is optional.')
    parser.add_argument('--ip', help='Give IP to use.')
    parser.add_argument('--mac', help='Give mac to use.')
    parser.add_argument('--verbose',
                        '-v',
                        action='count',
                        help='more output',
                        default=0)

    args = parser.parse_args()

    logging.basicConfig(format='%(levelname)s:%(message)s')

    logging.getLogger().setLevel(logging.WARNING)
    if args.verbose == 1:
        logging.getLogger().setLevel(logging.INFO)
    elif args.verbose >= 2:
        logging.getLogger().setLevel(logging.DEBUG)
    return args


def clean_args(args):
    args = clean_hostlist(args)
    args = clean_hostname(args)
    logging.debug("Using hostname %s and hostlist %s." % (args.hostname, args.hostlist))
    return args


def clean_hostlist(args):
    """makes sure the hostlist file exists

    also set institute based on hostlist file
    """
    if not os.path.isfile(args.hostlist):
        newhostlist = './hostlists/' + args.hostlist
        if not os.path.isfile(newhostlist):
            logging.error("Neiter %s nor %s is a file." % (args.hostlist, newhostlist))
            sys.exit(10)
        else:
            logging.info("Using %s as hostlist." % newhostlist)
            args.hostlist = newhostlist
    args.institute = os.path.splitext(os.path.basename(args.hostlist))[0].split('-')[1]
    return args


def clean_hostname(args):
    h = args.hostname
    domain = '.kit.edu'
    if h.endswith(domain):
        args.fqdn = h
    else:
        args.fqdn = h + '.' + args.institute + domain
    instlist = ['itp', 'ttp', 'particle']
    for i in instlist:
        if h.startswith(i) and i != args.institute:
            logging.warning("Hostname prefix and institute of hostlist don't agree.")
    return args


def get_mac(oldmacs):
    print("Enter penny password if prompted.")
    macout = subprocess.check_output('./tools/get_last_mac.sh')
    macs = macout.split()
    macs = [m.decode() for m in macs]

    for m in macs:
        if m in oldmacs:
            logging.info("Found MAC %s that already exists as %s. Ignoring it." % (m, oldmacs[m]))
            macs.remove(m)

    if len(macs) == 0:
        logging.error("No MAC found")
        sys.exit(3)
    if len(macs) == 1:
        mac = macs[0]
        logging.info("Found MAC " + mac)
    else:
        mac = None
        while mac is None:
            print("Found MACs:")
            for ind, m in enumerate(macs):
                print("%s: %s" % (ind, m))
            inp = input("Enter id to continue, empty means top entry: ")
            if inp == "":
                mac = macs[0]
            else:
                try:
                    ind = int(inp)
                    if ind < 0:
                        raise IndexError
                    mac = macs[ind]
                except ValueError:
                    print("Please enter an integer.")
                except IndexError:
                    print("Please enter a value between 0 and %s" % str(len(macs) - 1))
    return mac


def get_ip(oldips, hostlist, filename):
    "Return a free IP matching the range in filename, that is not yet part for hostlist."
    header = hostlist.fileheaders[filename]
    ipstart, ipend = header['iprange']
    newip = get_next_ip(ipstart, ipend, oldips)
    return newip


def main():
    args = parse_args()
    args = clean_args(args)

    myhostlist = hostlist.YMLHostlist()
    oldhostnames = {alias: h for h in myhostlist for alias in h.aliases}

    if args.hostname in oldhostnames:
        logging.error("Hostname %s already exists: %s" % (args.hostname, oldhostnames[args.hostname]))
        sys.exit(2)

    oldips = {h.ip: h for h in myhostlist}
    if args.ip is not None:
        ip = args.ip
        if ip in oldips:
            logging.error("The given IP already exists: %s" % oldips[ip])
            sys.exit(6)
    else:
        filename = os.path.basename(args.hostlist)
        ip = str(get_ip(oldips, myhostlist, filename))
        if ip is None:
            logging.error("Could not find a free IP in correct range.")
            sys.exit(5)

    oldmacs = {h.mac: h for h in myhostlist if hasattr(h, 'mac')}
    if args.mac is not None:
        mac = args.mac
    else:
        mac = get_mac(oldmacs)

    user, end_date = "", ""
    if "notebook" in args.hostlist:
        sys.stdout.write("Enter user associated with notebook (leave empty to ignore): ")
        user = input()
        sys.stdout.write("Enter end_date for notebook in format YYYY-MM-DD (leave empty to ignore): ")
        end_date = input()

    hostline = """
  - hostname: %s
    mac: %s
    ip: %s""" % (args.hostname, mac, ip)
    if user:
        hostline += "\n    user: %s" % user
    if end_date:
        hostline += "\n    end_date: %s" % end_date

    print("Will add%s" % hostline)
    usercontinue = yes_no_query("Continue?", empty_means=True)
    if not usercontinue:
        sys.exit(4)

    with open(args.hostlist, 'a') as f:
        f.write(hostline + '\n')


if __name__ == '__main__':
    main()

# TODO: implement addind a host to queue
# 	if [ "$institute" == "itp" ] && [ "$group" == "desktops" ]; then
# 		echo -n "Register with condor master? [yes/no] "
# 		read commit
# 		if [ "$commit" != "yes" ] && [ "$commit" != "no" ] ; then
# 			die "Unrecognized option"
# 		fi
# 		if [ "$commit" == "yes" ] ; then
# 			echo "Registering host with SGE master ..."
# 			ssh root@itpcondor "/itp/admin/sbin/addqhost $host"
# 		fi
# 	fi

# 	if [ "$institute" == "itp" ] && [ "$group" == "clusternode" ]; then
# 		echo -n "Register with condor master? [yes/no] "
# 		read commit
# 		if [ "$commit" != "yes" ] && [ "$commit" != "no" ] ; then
# 			die "Unrecognized option"
# 		fi
# 		if [ "$commit" == "yes" ] ; then
# 			echo "Registering host with SGE master ..."
# 			ssh root@itpcondor "/itp/admin/sbin/addqhost --no-submit $host"
# 		fi
# 	fi
