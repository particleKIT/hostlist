#!/usr/bin/env python3
"Sync hostlist and builds config files for services."

from hostlist import buildfiles

__version__ = '1.0.1'

if __name__ == "__main__":
    buildfiles.main()
