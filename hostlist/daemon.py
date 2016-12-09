#!/usr/bin/env python3

# import types
# from distutils.util import strtobool
# import sys

import git
import logging
import datetime
import cherrypy

from . import hostlist
from . import cnamelist
from . import output_services
# from hostlist.config import CONFIGINSTANCE as Config


class Inventory():

    def __init__(self):
        try:
            self.repo = git.Repo('.')
        except git.InvalidGitRepositoryError:
            self.repo = git.Repo('../')
        self.last_update = None
        self.fetch_hostlist()

    def fetch_hostlist(self, timeout=600):
        if self.last_update and datetime.datetime.now() - self.last_update < datetime.timedelta(seconds=timeout):
            return
        self.last_update = datetime.datetime.now()

        pullresult = self.repo.remote().pull()[-1]
        if not pullresult.flags & pullresult.HEAD_UPTODATE:
            logging.error("Failed to pull hosts repo.")
        self.hostlist = hostlist.YMLHostlist()
        self.cnames = cnamelist.FileCNamelist()
        print("Refreshed cache.")

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def ansible(self):
        self.fetch_hostlist()
        return output_services.AnsibleOutput.gen_content(self.hostlist, self.cnames)

    @cherrypy.expose
    def munin(self):
        self.fetch_hostlist()
        return output_services.MuninOutput.gen_content(self.hostlist, self.cnames)

    @cherrypy.expose
    def dhcp(self):
        self.fetch_hostlist()
        return output_services.DhcpOutput.gen_content(self.hostlist, self.cnames)

    @cherrypy.expose
    def hosts(self):
        self.fetch_hostlist()
        return output_services.HostsOutput.gen_content(self.hostlist, self.cnames)

    @cherrypy.expose
    def ethers(self):
        self.fetch_hostlist()
        return output_services.EthersOutput.gen_content(self.hostlist, self.cnames)

    @cherrypy.expose
    def status(self):
        result = 'Have a hostlist with %s hosts and %s cnames.' % (len(self.hostlist), len(self.cnames))
        result += '\nLast updated: %s' % self.last_update
        return result

    @cherrypy.expose
    @cherrypy.config(**{'tools.caching.delay': 10})
    def refreshcache(self):
        cherrypy.lib.caching.cherrypy._cache.clear()
        self.fetch_hostlist(timeout=10)

    @cherrypy.expose
    def index(self):
        return 'See <a href="https://github.com/particleKIT/hostlist">github.com/particleKIT/hostlist</a> how to use this API.'


def _auth_config(app):
    if app.config.get('/', {}).get('tools.auth_digest.on', False):
        users = app.config['authentication']
        app.config['/'].update({'tools.auth_digest.get_ha1': cherrypy.lib.auth_digest.get_ha1_dict_plain(users)})
    elif app.config.get('/', {}).get('tools.auth_basic.on', False):
        users = app.config['authentication']

        def check_pass(realm, user, password):
            if user not in users:
                return False
            else:
                return users[user] == password
        app.config['/'].update({'tools.auth_basic.checkpassword': check_pass})


def main():
    cherrypy.config.update('daemon.conf')
    app = cherrypy.tree.mount(Inventory(), '/', 'daemon.conf')
    _auth_config(app)
    cherrypy.engine.signals.subscribe()
    cherrypy.engine.start()
    cherrypy.engine.block()


if __name__ == '__main__':
    main()
