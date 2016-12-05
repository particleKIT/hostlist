#!/usr/bin/env python3

import yaml
import logging


class Config(dict):
    "provides access to config settings"
    CONFIGNAME = "config.yml"

    def __init__(self):
        self._loaded = False

    def __getitem__(self, *args):
        if not self._loaded:
            self.load()
        return dict.__getitem__(self, *args)

    def load(self):
        "read config from file"
        try:
            with open(self.CONFIGNAME, 'r') as configfile:
                self.update(yaml.safe_load(configfile))
            logging.info("loaded " + self.CONFIGNAME)
            self._loaded = True
        except:
            logging.error("failed to load " + self.CONFIGNAME)
            self._loaded = False
        return self._loaded


CONFIGINSTANCE = Config()
