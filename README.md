# hostlist

Hostlist reads yaml lists with information about hosts and generates
config files and inventory for several services.


## Quickstart

Example input files are in the ``tests`` directory. Hostlists are defined in the ``hostslists`` subdirectory, where the filename
encodes the ``hosttype`` and ``institute`` attributes of the contained hosts.

Run ``buildfiles`` to generate the output.
``buildfiles --help`` shows the available options.

## Configuration

The main configuration is in ``config.yml`` in the working directory. 
Hostlists are collected in a directory listed in ``config.yml``.


## Format of hostlists

The hostlists are files under ``hostlists``. The file format is either
``hosttype-institute.yml`` or ``hosttype.yml``, i.e. 0 or 1 dash. The filename will
be parsed and set as institute/hosttype for all hosts in that file.

The hostlists are in yaml. Multiple yaml documents in one file are allows. Each
yaml document starts with a line containing only ``---``.

Each yaml document document has a ``header`` and a list of ``hosts``.
The header has to have an iprange, that lists the allowed range for the hosts in
the file. It can also set variables and groups.

The hostlist is a list of dicts, which each need a hostname and an ip and can
take other variables.

## Variables and Groups

Each host has a list of variables (dict) associated with it as well as a list of groups (set).

If variables are set in multiple places they are overwritten in this order:
filename < header < host

For groups a default is set in the config file. 
In the header and the host definition one can define lists ``groups`` and ``notgroups`` that are added/subtracted from the list of
groups for that host.

Groups are used to define which hosts are used in some outputs (muninnode, ssh_known_hosts) or which hosts should be included for
checks (needs_ip, needs_mac).


## Checks

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
  
To ignore failed tests list them in the ``ignore_checks`` list in your ``config.yml``:
```yaml
ignore_checks:
    - "end_date"
    - "user"
    - "nonunique"
    - "cnames"
    - "duplicates"
    - "missing_mac_ip"
    - "iprange_overlap"
``` 

## Services

At the moment the supported services are:

* /etc/hosts, can also be used for dnsmasq
* dhcpd
* ansible inventory
* munin 
* ssh_known_hosts generation


## Web daemon

You can start ``hostlist-daemon`` to serve the generated content (dns,dhcp,munin,...) via http. Start ``hostlist-daemon`` where you would run ``buildfiles``. The web daemon is based on cherrypy and has a config file daemon.conf.
  
In addition there is a human readable web page generated with [ansible-cmdb](https://github.com/fboender/ansible-cmdb). Optional settings for ansible-cmd are:
```yaml
ansible_cmdb:
  columns:
    - name
    - ram
    - comment
    - main_ip
  template: 'fancy_html'
  data: 
  fact_dirs:
    - facts
```
  
which can be tested by viewing the output of ``buildfiles --web > index.html`` in a web browser. 
Note that if you want to have various host variables listed you must add them to the ``ansiblevars`` dict in the config.yml in order to have them in the ansible inventory. 
Since buildfiles does not execute ansible on any remote host, there are no host facts (ram,cpu,vendors,disk usage...) available. However, one can supply these informations via fact caching from previous ansible runs via the directories listed in ``fact_dirs`` (see the ansible-cmdb documentation).


## Example

A working example for inputs and all configuration files can be found in ``tests``.


## DNSVS Synchronization

Besides generating config files, the hostlist can also be synchronized against
DNSVS, which is the dns management system used by https://www.scc.kit.edu.

In order to use the DNSVS interface you need an API token , which is expected in ~/.config/netdb_client.ini. In order to generate the token, log-in/got-to https://netvs.scc.kit.edu/user/tokens.

With the token-file added, you can run ``buildfiles``, which shows you a
diff between dnsvs and the local files and gives the option to copy the local
hostlist to dnsvs.


## Tests
To run the tests:
::

  cd tests; py.test

## Contribute
Feel free to use the code and adjust it to your needs.
Pull requests are welcome!

## Style guide

The code should obey PEP8 (as enforced by flake8 or pylint) when possible.
