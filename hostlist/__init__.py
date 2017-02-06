#!/usr/bin/env python3
"Sync hostlist and builds config files for services."

from . import buildfiles

__version__ = '1.3.0'

if __name__ == "__main__":
    buildfiles.main()
