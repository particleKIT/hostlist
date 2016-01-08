#!/bin/env python3


import logging
import subprocess
# import distutils.util
import re
from collections import namedtuple
# import json
# import os
# import paramiko
# import base64


class InvalidLineException(Exception):
    pass


class dnsvs_interface:

    dnsvs_host = "dns-robot@dnsvs.scc.kit.edu"

    def execute(self, command):
        """runs command and returns the produced string"""
        p = subprocess.Popen(["ssh", self.dnsvs_host],
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
        self.ssh_connection = p

        if command.__class__ in [list, tuple]:
            command = '\n'.join(command)
        format_command = bytes(command, 'utf8')
        output, stderr = self.ssh_connection.communicate(input=format_command)
        output = output.decode('utf8')
        annotated = self.annotate(output)
        return annotated

    def execute_success(self, command):
        res = self.execute(command)
        if not res.success:
            raise Exception("DNSVS command '" + command +
                            "' failed with " + str(res))

    def parse(self, output):
        lines = str(output).splitlines()
        parsed_output = [self.parse_line(line)
                         for line in lines
                         if not line.startswith("Pseudo-terminal")]
        return parsed_output

    def parse_line(self, line):
        line_regexp = re.compile('(\d{3})([ -])(.*)')
        Line_tup = namedtuple('Line_tup', ['code', 'sep', 'text'])
        # logging.debug('working on line')
        # logging.debug(line)
        re_res = re.match(line_regexp, line)
        if re_res is None:
            return Line_tup(501, False, "")
        code, sep, text = re_res.groups()
        return Line_tup(int(code), sep == '-', text)

    def annotate(self, output):
        parsed = self.parse(output)
        success = parsed[-1].code == 210 and parsed[-2].code in [200, 201]
        DNSVS_result = namedtuple('DNSVS_result',
                                  ['success', 'parsedoutput', 'rawoutput'])

        return DNSVS_result(success, parsed, output)

    def get_hosts(self, namespace):
        out = self.execute(['rng '+namespace, 'list a1'])
        if not out.success:
            print(out.rawoutput)
            raise Exception("unexpected ouput")
        hosts = self.parse_hostlist(out.parsedoutput)
        return hosts

    def parse_hostlist(self, output):
        hosts = {}
        ipregexp = r'a1: (.*)\.\s*((?:[0-9]{1,3}\.){3}[0-9]{1,3})'
        line_regexp = re.compile(ipregexp)
        for line in output:
            # only consider a1 output lines
            if line.code != 260:
                continue
            # ignore empty blocks (happens only for empty namespaces)
            # workaroung for bug in dnsvs
            if line.text == 'a1':
                continue
            matchres = re.match(line_regexp, line.text)
            if matchres is None:
                logging.warning("could not find match in: "+str(line.text))
                continue
            hostname, ip = matchres.groups()
            hosts[hostname] = ip
        return hosts

    def add_host(self, host):
        """add a new host"""
        # wanted string:
        # new a1 test1 193.196.62.1 UNIX
        command_template = "rng_by_addr {ip}\nnew a1 {hostname}. {ip}"
        command = command_template.format(hostname=host.fqdn, ip=host.ip)
        self.execute_success(command)

    def remove_host(self, host):
        """remove a host"""
        # wanted string:
        # del a1 test1 193.196.62.1 UNIX
        command_template = "rng_by_addr {ip}\ndel a1 {hostname}. {ip}"
        command = command_template.format(hostname=host.fqdn, ip=host.ip)
        self.execute_success(command)


if __name__ == "__main__":
    logging.basicConfig(format='%(levelname)s:%(message)s')

    logging.getLogger().setLevel(logging.DEBUG)
    d = dnsvs_interface()
