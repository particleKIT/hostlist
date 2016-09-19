# hostlist

Hostlist reads yaml lists with information about hosts and from that generates
config files and inventory for several services.

## Services

At the moment the supported services are:
* /etc/hosts, can also be used for dnsmasq
* dhcpd
* ansible inventory
* munin 
* ssh_known_hosts generation

## DNSVS Synchronization

Besides generating config files, the hostlist can also be synchronized against
DNSVS, which is the dns management system used by https://www.scc.kit.edu.

## Tests
To run the unit tests:
  nosetest tests

## Contribute
Feel free to use the code and adjust it to your needs.
Pull requests are welcome!
