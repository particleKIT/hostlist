hostlist
========

Hostlist reads yaml lists with information about hosts and generates
config files and inventory for several services.


Quickstart
----------

Example input files are in the `tests` directory. Hostlists are defined in the `hostslists` subdirectory, where the filename
encodes the `hosttype` and `institute` attributes of the contained hosts.

Run `buildfiles` to generate the output.
`buildfiles --help` shows the available options.

Configuration
-------------

The main configuration is in ``config.yml`` in the working directory. 
Hostlists are collected in a directory listed in ``config.yml``.

Services
--------

At the moment the supported services are:

* /etc/hosts, can also be used for dnsmasq
* dhcpd
* ansible inventory
* munin 
* ssh_known_hosts generation


Web daemon
----------

You can start `hostlist-daemon` to serve the generated content via http. Start `hostlist-daemon` where you would run `buildfiles`
and 

DNSVS Synchronization
---------------------

Besides generating config files, the hostlist can also be synchronized against
DNSVS, which is the dns management system used by https://www.scc.kit.edu.

Tests
-----
To run the unit tests:
::

  nosetest tests

Contribute
----------
Feel free to use the code and adjust it to your needs.
Pull requests are welcome!

Style guide
-----------

The code should obey PEP8 (as enforced by flake8 or pylint) when possible.
