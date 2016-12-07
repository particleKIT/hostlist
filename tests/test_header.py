#!/usr/bin/env python3

from hostlist import hostlist
from hostlist import cnamelist


class TestGroup():
    def setup(self):
        self.hosts = hostlist.YMLHostlist()
        self.cnames = cnamelist.FileCNamelist()

    def testgroups(self):
        serv3 = list(filter(lambda x: x.fqdn == 'serv3.abc.example.com', self.hosts))[0]
        assert serv3 in self.hosts.groups['newservertype']
