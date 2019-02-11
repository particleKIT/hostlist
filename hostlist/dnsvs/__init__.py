#!/usr/bin/python3

import requests
import json
import os.path
import logging
from typing import Optional, Dict, Tuple, List

from ..host import Host
from ..cnamelist import CName


class DNSVSInterface:

    certfilename = '~/.ssl/net-webapi.key'
    certfilename = os.path.expanduser(certfilename)
    root_url = 'https://www-net.scc.kit.edu/api/2.1/dns'
    geturl = root_url + '/record/list'
    createurl = root_url + '/record/create'
    deleteurl = root_url + '/record/delete'
    # all our entries ar IPv4
    inttype_a = "dflt:0100,:,403,A"
    inttype_nonunique = "dflt:1100,:,400,A"
    inttype_cname = "alias:0000,dflt:0100,011,CNAME"

    headers_dict = {"Content-Type": "application/json"}

    def _execute(self, url: str, method: str, data: Optional[str]=None) -> List:
        """Actually perform an operation on the DNS server."""
        try:
            if method == "get":
                response = requests.get(url=url, headers=self.headers_dict, cert=self.certfilename)
            elif method == "post":
                response = requests.post(url=url, data=data, headers=self.headers_dict, cert=self.certfilename) # type: ignore
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
        result = self._execute(self.geturl, method="get")
        # continue with normal request (process result)
        hosts = {}
        for entry in result:
            fqdn = entry['fqdn'].rstrip(".")
            if entry['type'] == 'A':
                is_nonunique = entry['inttype'] == self.inttype_nonunique
                hosts[fqdn] = (entry['data'], is_nonunique)
        return hosts

    def get_cnames(self) -> Dict[str, str]:
        """Reads CNAME records from the server."""
        result = self._execute(self.geturl, method="get")
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

        inttype = self.inttype_nonunique if not host.vars['unique'] else self.inttype_a
        data = [
            {"param_list": [
                {"name": "fqdn", "new_value": host.fqdn },
                {"name": "inttype", "new_value": inttype},
                {"name": "data", "new_value": str(host.ip)}
            ]},
        ]
        json_string = json.dumps(data, ensure_ascii = False)
        self._execute(url=self.createurl, method="post", data=json_string)

    def remove_host(self, host: Host) -> None:
        """Remove an A record from the server."""
        # TODO: handle these errors in the response
        # before removing, check whether a cname points to that record
        # https://www-net.scc.kit.edu/api/2.0/dns/record/list?target_fqdn_regexp=ttpseth.ttp.kit.edu.
        # url = self.root_url+"/record/list?type=CNAME&target_fqdn="+host.fqdn+"."
        # dependencies = self._execute(url=url, method="get")
        # if dependencies!=[]:
        #     raise Exception('Attempting to remove an A record of a host to which a cname ist pointing.')
        # url = self.root_url+"/record/list?type=A&fqdn="+host.fqdn+"."
        # dnsvs_records = self._execute(url=url, method="get")
        # if dnsvs_records!=[]:
        #     if dnsvs_records[0]['data']!=str(host.ip):
        #         raise Exception('Attempting to remove an existing A record, for which the IP adress does not match.')
        # else:
        #     logging.warning('Attempting to remove a nonexistent A record.')
        #     return
        # remove
        # TODO: can we use host.fqdn/host.ip here?
        # trust our data more then theirs
        inttype = self.inttype_a if host.vars['unique'] else self.inttype_nonunique

        data = [
            {"param_list": [
                {"name": "fqdn", "old_value": host.fqdn + "."},
                {"name": "data", "old_value": str(host.ip)},
                {"name": "inttype", "old_value": inttype},
            ]},
        ]
        json_string = json.dumps(data)
        self._execute(url=self.deleteurl, method="post", data=json_string)

    def add_cname(self, cname: CName) -> None:
        """Adds a CNAME record given by (alias, hostname) to the server."""
        fqdn, dest = cname.fqdn, cname.dest
        # TODO: handle these errors in the response
        # check whether the cname record is already there
        # url = self.root_url+"/record/list?type=CNAME&target_fqdn_regexp="+dest+"."+"&fqdn="+fqdn+"."
        # dependencies = self._execute(url=url, method="get")
        # if dependencies!=[]:
        #     logging.warning('Attempting to add an already existing CNAME record to DNSVS!')
        #     return
        # else:
        #     # check whether there is a different CNAME record for the same fqdn
        #     url = self.root_url+"/record/list?type=CNAME&fqdn="+fqdn+"."
        #     dependencies = self._execute(url=url, method="get")
        #     if dependencies!=[]:
        #         raise Exception('Attempting to overwrite an existing CNAME record in DNSVS with a different one!')
        # # check whether there is an A record with the same fqdn
        # url = self.root_url+"/record/list?type=A&fqdn="+fqdn+"."
        # dependencies = self._execute(url=url, method="get")
        # if dependencies!=[]:
        #     raise Exception('Attempting to overwrite an A record in DNSVS with a CNAME record!')
        # url = self.root_url+"/record/list?type=A&fqdn="+dest+"."
        # inarecords = self._execute(url=url, method="get")
        # url = self.root_url+"/record/list?type=CNAME&fqdn="+fqdn+"."
        # incnames = self._execute(url=url, method="get")
        # if inarecords==[] and incnames==[]:
        #     raise Exception('Attempting to add a CNAME record do DNSVS pointing to a nonexistent fqdn!')
        # write
        data = [
            {"param_list": [
                {"name": "fqdn", "new_value": fqdn + "."},
                {"name": "data", "new_value": dest + "."},
                {"name": "inttype", "new_value": self.inttype_cname},
            ]},
        ]
        json_string = json.dumps(data)
        self._execute(url=self.createurl, method="post", data=json_string)

    def remove_cname(self, cname: CName) -> None:
        """Remove a CNAME record from the server."""
        fqdn, dest = cname.fqdn, cname.dest
        # TODO: handle these errors in the response
        # check whether the cname record is there in the first place
        # url = self.root_url+"/record/list?type=CNAME&target_fqdn_regexp="+dest+"."+"&fqdn="+fqdn+"."
        # dependencies = self._execute(url=url, method="get")
        # if dependencies == []:
        #     logging.warning('Attempting to remove a nonexistent CNAME record from DNSVS!')
        #     return
        # remove
        data = [
            {"param_list": [
                {"name": "fqdn", "old_value": fqdn + "."},
                {"name": "data", "old_value": dest + "."},
                {"name": "inttype", "old_value": self.inttype_cname},
            ]},
        ]
        json_string = json.dumps(data)
        self._execute(url=self.deleteurl, method="post", data=json_string)
