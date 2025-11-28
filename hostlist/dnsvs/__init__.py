#!/usr/bin/python3

import requests
import json
import os.path
import logging
import urllib.parse
from typing import Optional, Dict, Tuple, List
from configparser import ConfigParser
from ..host import Host
from ..cnamelist import CName

def encode_list_query_param(values):
    return urllib.parse.quote(json.dumps(values))

class DNSVSInterface:

    try:
        configfile = os.path.expanduser('~/.config/netdb_client.ini')
        config = ConfigParser()
        config.read(configfile)
        token = config['prod']['token']
    except KeyError:
        logging.error("No token file found. Also make sure that "
                      "a [prod] section with a 'token = value' assignment exists.")
        token = ''
    root_url = 'https://www-net.scc.kit.edu/api/4.2/dns'
    geturl = root_url + '/record/list'
    createurl = root_url + '/record/create'
    deleteurl = root_url + '/record/delete'
    fqdn_createurl = root_url + '/fqdn/create'

    headers_dict = {"accept": "application/json", "Content-Type": "application/json", 'Authorization': 'Bearer ' + token}

    def _execute(self, url: str, method: str, data: Optional[str] = None) -> List:
        """Actually perform an operation on the DNS server."""
        try:
            if method == "get":
                response = requests.get(url=url, headers=self.headers_dict)
            elif method == "post":
                response = requests.post(url=url, data=data, headers=self.headers_dict) # type: ignore
            if response.ok:
                return response.json()
            else:
                raise requests.exceptions.RequestException(response.status_code, response.text)
        except Exception as e:
            logging.error(str(e))
            raise
        return []

    def get_hosts(self) -> Dict[str, Tuple[str, bool]]:
        """Reads A records from the server."""
        result = self._execute(self.geturl, method="get")[0]
        # continue with normal request (process result)
        hosts = {}
        for entry in result:
            fqdn = entry['fqdn'].rstrip(".")
            if entry['type'] == 'A':
                is_nonunique = not entry['target_is_reverse_unique']
                hosts[fqdn] = (entry['data'], is_nonunique)
        return hosts

    def get_cnames(self) -> Dict[str, str]:
        """Reads CNAME records from the server."""
        result = self._execute(self.geturl, method="get")[0]
        # continue with normal request (process result)
        cname = {}
        # cname = {
        #     entry['fqdn'].rstrip("."): entr["data"].rstrip(".")
        #     for entry in result if entry["type"] == 'CNAME'
        # }
        for entry in result:
            fqdn = entry['fqdn'].rstrip(".")
            if entry['type'] == 'CNAME':
                cname[fqdn] = entry['data'].rstrip(".")
        return cname

    def add(self, entry):
        """generic interface to add_*"""
        if isinstance(entry, Host):
            self.add_host(entry)
        elif isinstance(entry, CName):
            self.add_cname(entry)

    def remove(self, entry):
        """generic interface to remove_*"""
        if isinstance(entry, Host):
            self.remove_host(entry)
        elif isinstance(entry, CName):
            self.remove_cname(entry)

    def add_host(self, host: Host) -> None:
        """Adds an A record to the server."""

        #fqdn = host.fqdn.rstrip('.')  # Ensure no trailing dot
        fqdn = host.fqdn + "."
        fqdn_list = encode_list_query_param([fqdn])
        #type_list = encode_list_query_param(["A"])


        # Step 0: ensure no A record for that exists
        #url = f"{self.root_url}/record/list?fqdn_list={fqdn_list}&type_list={type_list}"
        #dependencies = self._execute(url=url, method="get")

        #print(dependencies)
        #if dependencies:
            #if dependencies[0]['data'] == str(host.ip):
                #logging.warning('Attempting to add an already existing A record.')
                #return
            #else:
                #raise Exception('Trying to overwrite existing A record with different IP.')

        # Step 1: ensure FQDN exists
        url = f"{self.root_url}/fqdn/list?value_list={fqdn_list}"
        fqdns = self._execute(url=url, method="get")
        if not fqdns or not any(fqdns):
            logging.info(f"FQDN '{fqdn}' not found. Creating it.")
            fqdn_data = {
                "new": {
                    "value": fqdn,
                    "type": "domain",
                }
            }
            self._execute(url=self.fqdn_createurl, method="post", data=json.dumps(fqdn_data))

        # Step 2: create A record
        data = {
            "new": {
                "data": str(host.ip),
                "fqdn": fqdn,
                "type": "A",
                "target_is_reverse_unique": host.vars['unique']
            }
        }
        self._execute(url=self.createurl, method="post", data=json.dumps(data))

    def remove_host(self, host: Host) -> None:
        """Remove an A record from the server."""
        # TODO: before removing, check whether a cname points to that record
        data = { "old": {
                "data": str(host.ip),
                "fqdn": host.fqdn + '.',
                "type": 'A'
                }
        }
        json_string = json.dumps(data)
        self._execute(url=self.deleteurl, method="post", data=json_string)

    def add_cname(self, cname: CName) -> None:
        """Adds a CNAME record given by (alias, hostname) to the server."""
        fqdn, dest = cname.fqdn, cname.dest
        # TODO: check whether the cname record is already there and the fqdn exists
        data = {"new": {
                "fqdn": fqdn + ".",
                'type': 'CNAME',
                "data": dest + ".",
                "target_is_reverse_unique": False}
                }
        json_string = json.dumps(data)
        self._execute(url=self.createurl, method="post", data=json_string)

    def remove_cname(self, cname: CName) -> None:
        """Remove a CNAME record from the server."""
        fqdn, dest = cname.fqdn, cname.dest
        # TODO: check whether the cname record is there in the first place
        data = {"old": {
                "fqdn": fqdn + ".",
                'type': 'CNAME',
                "data": dest + "."}
                }
        json_string = json.dumps(data)
        self._execute(url=self.deleteurl, method="post", data=json_string)
