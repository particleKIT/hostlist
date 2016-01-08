import inventory_lib


class TestSimpleHost():
    def setup(self):
        self.host = inventory_lib.Host('confline',
                                       "host=host1.abc.kit.edu \
                                        mac=00:12:34:ab:CD:EF \
                                        ip=127.0.0.1",
                                       "abc",
                                       "desktops")

    def testOutput(self):
        print(self.host.dhcp)
        assert self.host.hostname == 'host1.abc.kit.edu'
        assert self.host.mac == '00:12:34:ab:cd:ef'
        assert self.host.ip == '127.0.0.1'
        assert self.host.aliases == ['host1.abc.kit.edu', 'host1']
        assert self.host.dhcp == """host host1.abc.kit.edu {
        hardware ethernet 00:12:34:ab:cd:ef;
        fixed-address 127.0.0.1;
        option host-name "host1.abc.kit.edu";
        option domain-name "abc.kit.edu";
        }"""
