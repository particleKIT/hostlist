# Change Log

## 1.4.0

### Added
* improved web-overview for available services
* web-hostlist no based on ansible-cmdb: https://github.com/fboender/ansible-cmdb

## 1.3.2

### Added
* config var to ignore failed checks

## 1.3.0

### Added
* add /list page in daemon with a table of hosts
* type annotations for mypy

### Changed
* Use groups for need_*, gen_* instead of hardcoded variables

### Fixed
* in consistency check on yml input, not synced hostlist
* have daemon continue running also when git pull fails

## 1.2.0

### Added
* output information about hosts, when given as arguments to buildfiles
  * can give hostname or group as argument
  * multiple arguments are allowed (combined via or)
  * output verbosity can change from
    * `-q`: only list of hostnames
    * default: hostnames and groups
    * `-v`: all information on hosts including all variables

## 1.1.0

### Added
* daemon (hostlist-daemon)
  * distribute inventories via http(s)
  * Dockerfile to run the daemon
  * pulls repo updates and caches result
  * http basic/digest authentication
* allow to set groups (via variable `groups` as a list of strings)
* more tests, work with py.test

### Changed
* remove deploy code
* remove `build` directory, copying files replaced by http daemon
* remove flag `--stdout`, this is now default when running buildfiles with a service argument
* no explicit checks during DNSVS sync, rely on internal consistency checks

### Fixed
* Failure to update changing IPs on sync with DNSVS in the diff part

## 1.0.2

### Added
* proper python package
* first version on pypi
* use flit for packaging

## 1.0.0 - 2016-09-19

### Added
* initial public version
* yml input format
