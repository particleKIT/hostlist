#!/usr/bin/env python3
from hostlist import host
import ipaddress


class TestSimpleHost():
    def setup(self):
        self.host = host.YMLHost(
            {
                'hostname': 'host1.abc.example.com',
                'mac': '00:12:34:ab:CD:EF',
                'ip': '198.51.100.2',
            },
            "desktops",
            "abc",
        )

    def testOutput(self):
        assert self.host.hostname == 'host1.abc.example.com'
        assert self.host.mac == host.MAC('00:12:34:ab:cd:ef')
        assert self.host.ip == ipaddress.ip_address('198.51.100.2')
        assert self.host.aliases == ['host1.abc.example.com', 'host1']
