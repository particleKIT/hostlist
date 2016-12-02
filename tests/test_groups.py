#!/usr/bin/env python3

from hostlist import hostlist
from hostlist import cnamelist
from hostlist import output_services
from pprint import pprint


class TestGroup():
    def setup(self):
        self.hosts = hostlist.YMLHostlist()
        self.cnames = cnamelist.FileCNamelist()

    def testgroups(self):
        host3candidates = list(filter(lambda x: x.fqdn == 'host3.abc.example.com', self.hosts))
        assert len(host3candidates) == 1
        host3 = host3candidates[0]
        host4 = list(filter(lambda x: x.fqdn == 'host4.abc.example.com', self.hosts))[0]
        assert host3 in self.hosts.groups['headergroup']
        assert host4 not in self.hosts.groups['headergroup']
        assert host3 in self.hosts.groups['extragroup']
        assert host4 in self.hosts.groups['othergroup']

    def testservergroup(self):
        assert self.hosts.groups['superserver'][0].fqdn == 'serv1.abc.example.com'
        assert len(self.hosts.groups['superserver']) == 1

    def testansiblegroups(self):
        ansout = output_services.AnsibleOutput().gen_content(self.hosts, self.cnames)
        data = dict(ansout)
        pprint(data)
        assert data['_meta']['hostvars']['host4.abc.example.com']['ip'] == '198.51.100.4'
        assert data['server']['hosts'] == ['serv1.abc.example.com']
        assert data['superserver']['hosts'] == ['serv1.abc.example.com']
        assert data['serverheadergroup']['hosts'] == ['serv1.abc.example.com']
        assert data['blubberinst']['hosts'] == ['serv1.abc.example.com']
