#!/usr/bin/env python3

# import types
# from distutils.util import strtobool
# import sys

import cherrypy

from . import hostlist
from . import cnamelist
from . import output_services
# from hostlist.config import CONFIGINSTANCE as Config


class HostAPI():

    def get_hostlist(self):
        self.hosts = hostlist.YMLHostlist()
        self.cnames = cnamelist.FileCNamelist()

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def ansible(self):
        self.get_hostlist()
        return output_services.AnsibleOutput.gen_content(
            self.hosts,
            self.cnames,
        )

    @cherrypy.expose
    def munin(self):
        self.get_hostlist()
        return output_services.MuninOutput.gen_content(
            self.hosts,
            self.cnames,
        )

    @cherrypy.expose
    def index(self):
        self.get_hostlist()
        return 'See <a href="https://github.com/particleKIT/hostlist">github.com/particleKIT/hostlist</a> how to use this API.'


def main():
    cherrypy.quickstart(HostAPI())


if __name__ == '__main__':
    main()
