# Change Log

## 1.1.0 - unrelease

### Added
* daemon (hostlist-daemon)
  * distribute inventories (esp. ansible/munin) via http
  * Dockerfile to run the daemon

### Changed
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
