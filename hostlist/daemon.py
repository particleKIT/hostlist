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
    @cherrypy.tools.accept(media='text/plain')
    def ansible(self):
        self.get_hostlist()
        return output_services.AnsibleOutput.gen_content(
            self.hosts,
            self.cnames,
        )

    @cherrypy.expose
    @cherrypy.tools.accept(media='text/plain')
    def munin(self):
        self.get_hostlist()
        return output_services.MuninOutput.gen_content(
            self.hosts,
            self.cnames,
        )


def main():
    cherrypy.quickstart(HostAPI())


if __name__ == '__main__':
    main()
