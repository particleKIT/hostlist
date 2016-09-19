#!/usr/bin/env python3
import host
import ipaddress


class TestSimpleHost():
    def setup(self):
        self.host = host.YMLHost(
            {
                'hostname': 'host1.abc.kit.edu',
                'mac': host.MAC('00:12:34:ab:CD:EF'),
                'ip': ipaddress.ip_address('192.168.0.1'),
            },
            "desktops",
            "abc",
        )

    def testOutput(self):
        assert self.host.hostname == 'host1.abc.kit.edu'
        assert self.host.mac == host.MAC('00:12:34:ab:cd:ef')
        assert self.host.ip == ipaddress.ip_address('192.168.0.1')
        assert self.host.aliases == ['host1.abc.kit.edu', 'host1']
