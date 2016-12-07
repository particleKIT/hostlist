hostlist
========

Hostlist reads yaml lists with information about hosts and generates
config files and inventory for several services.


Quickstart
----------

Example input files are in the ``tests`` directory. Hostlists are defined in the ``hostslists`` subdirectory, where the filename
encodes the ``hosttype`` and ``institute`` attributes of the contained hosts.

Run ``buildfiles`` to generate the output.
``buildfiles --help`` shows the available options.

Configuration
-------------

The main configuration is in ``config.yml`` in the working directory. 
Hostlists are collected in a directory listed in ``config.yml``.


Format of hostlists and special fields
--------------------------------------

The hostlists are files under ``hostlists``. The file format is either
``hosttype-institute.yml`` or ``hosttype.yml``, i.e. 0 or 1 dash. The filename will
be parsed and set as institute/hosttype for all hosts in that file.

The hostlists are in yaml. Multiple yaml documents in one file are allows. Each
yaml document starts with a line containing only ``---``.

Each yaml document document has a ``header`` and a list of ``hosts``.
The header has to have an iprange, that lists the allowed range for the hosts in
the file. It can also set variables, that will then be used for hosts, like
needs_mac, gen_munin, ansible, ...

The hostlist is a list of dicts, which each need a hostname and an ip and can
take other variables.

If variables are set in multiple places they are overwritten in this order:
filename < header < host


Checks
------

Many checks are performed to ensure consistency and find mistakes before they
are deployed:

* IP range

  * hosts must have an IP in the given range
  * all hosts must fall into the IP ranges stated in the config
  * ipranges between files must not overlap (except iprange_allow_overlap is set)
  
* IP, MAC and hostname must be unique
* if ``user`` is set, it must be an existing user account (to detect machines
  belonging to users who no longer have an account)
* if ``end_date`` is set, it must be in the future


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

You can start ``hostlist-daemon`` to serve the generated content via http. Start ``hostlist-daemon`` where you would run ``buildfiles``.
The daemon is based on cherrypy and has a config file daemon.conf. 


Example
-------

A working example for inputs and all configuration files can be found in ``tests``.


DNSVS Synchronization
---------------------

Besides generating config files, the hostlist can also be synchronized against
DNSVS, which is the dns management system used by https://www.scc.kit.edu.

In order to use the DNSVS interface you need a ssl-key, which is expected in ~/.ssl/net-webapi.key. In order to generate the key, follow the instructions in the section "Hinweise zur Zertifikatsbenutzung bzw. Registrierung" at the bottom of the page https://www-net-doku.scc.kit.edu/webapi/2.0/intro.

With the key added, you can run ``buildfiles``, which shows you a
diff between dnsvs and the local files and gives the option to copy the local
hostlist to dnsvs.


Tests
-----
To run the tests:
::

  cd tests; py.test

Contribute
----------
Feel free to use the code and adjust it to your needs.
Pull requests are welcome!

Style guide
-----------

The code should obey PEP8 (as enforced by flake8 or pylint) when possible.
