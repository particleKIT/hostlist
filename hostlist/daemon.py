#!/usr/bin/env python3

# import types
# from distutils.util import strtobool
# import sys

import cherrypy
import git

from . import hostlist
from . import cnamelist
from . import output_services
# from hostlist.config import CONFIGINSTANCE as Config


class Inventory():

    def __init__(self):
        self.repo = git.cmd.Git('.') 

    def get_hostlist(self):
        self.repo.pull()
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
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 80,
    })
    cherrypy.quickstart(Inventory())


if __name__ == '__main__':
    main()
