#!/usr/bin/python3

import requests
import json
import os.path
import logging
from typing import Optional, Dict, Tuple, List
from configparser import ConfigParser
from ..host import Host
from ..cnamelist import CName

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
    root_url = 'https://www-net.scc.kit.edu/api/3.0/dns'
    geturl = root_url + '/record/list'
    createurl = root_url + '/record/create'
    deleteurl = root_url + '/record/delete'

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
        # TODO: handle these errors in the response
        # check whether there is already a CNAME with that fqdn
        # url = self.root_url+"/record/list?type=CNAME&fqdn="+host.fqdn+"."
        # dependencies = self._execute(url=url, method="get")
        # if dependencies!=[]:
        #     raise Exception('Attempting to overwrite an existing CNAME record in DNSVS with an A record!')
        # url = self.root_url+"/record/list?type=A&fqdn="+host.fqdn+"."
        # dependencies = self._execute(url=url, method="get")
        # if dependencies!=[]:
        #     if dependencies[0]['data']==str(host.ip):
        #         logging.warning('Attempting to add already an existing A record.')
        #         return
        #     elif dependencies[0]['data']!=str(host.ip):
        #         raise Exception('Attempting to overwrite an existing A record with a different one.')

        data = { "new": {
                "data": str(host.ip),
                "fqdn": host.fqdn + '.',
                "type": 'A',
                "fqdn_type": 'host',
                "target_is_reverse_unique": host.vars['unique']
                }
        }
        json_string = json.dumps(data, ensure_ascii = False)
        self._execute(url=self.createurl, method="post", data=json_string)

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
                "fqdn_type": 'alias',
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
