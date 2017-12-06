#!/usr/bin/env python3

# import types
# from distutils.util import strtobool
# import sys

import git
import datetime
import cherrypy
from cherrypy import log

from . import hostlist
from . import cnamelist
from .output_services import Output_Services
from .config import CONFIGINSTANCE as Config

class Inventory():

    def __init__(self):
        try:
            self.repo = git.Repo('.')
        except git.InvalidGitRepositoryError:
            self.repo = git.Repo('../')
        self.last_update = None
        self.fetch_hostlist()
        self.pull_failed = False

    def fetch_hostlist(self, timeout=600):
        if self.last_update and datetime.datetime.now() - self.last_update < datetime.timedelta(seconds=timeout):
            return
        self.last_update = datetime.datetime.now()

        try:
            pullresult = self.repo.remote().pull()[-1]
            if not pullresult.flags & pullresult.HEAD_UPTODATE:
                self.pull_failed = True
                log("Hosts repo not up to date after pull.")
        except:
            log("Failed to pull hosts repo.")
            self.pull_failed = True
        Config.load()
        self.hostlist = hostlist.YMLHostlist()
        self.cnames = cnamelist.FileCNamelist()
        self.pull_failed = False
        print("Refreshed cache.")

    def _cp_dispatch(self,vpath):
        if len(vpath) == 0:
            cherrypy.request.params['service'] = "index"
            return self
        param = vpath.pop(0)
        if param in Output_Services:
            cherrypy.request.params['service'] = param
        return self

    @cherrypy.expose
    @cherrypy.config(**{'tools.caching.delay': 10})
    def refreshcache(self):
        cherrypy.lib.caching.cherrypy._cache.clear()
        self.fetch_hostlist(timeout=10)

    @cherrypy.expose
    def index(self, service='index'):
        if service != 'index':
            return Output_Services[service](self.hostlist, self.cnames)
        servicelist = sorted(list(Output_Services.keys()))
        branch = self.repo.active_branch
        out = 'Last update: ' + str(self.last_update)
        out += ' <b>(failed)</b><br>' if self.pull_failed else '<br>'
        out += 'Branch:{0}<br>Commit:{1} <b>{2}</b> ({3})<br><br>'.format(
                str(branch),
                str(branch.commit),
                str(branch.commit.summary),
                str(branch.commit.author)
                )
        out += 'Available hostlists:<br>'
        out += ''.join(list(map(lambda s: '<a href="/{0}">{0}</a><br>'.format(s), servicelist)))
        out += '<br><br><i>See <a href="https://github.com/particleKIT/hostlist">github.com/particleKIT/hostlist</a> how to use this API.</i>'
        return out


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
