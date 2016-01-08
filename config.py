#!/usr/bin/env python3

import yaml
import logging


class Config:
    configname = "config.yml"
    _loaded = False

    def load_config(self):
        with open(self.configname, 'r') as configfile:
            Config.cfg = yaml.safe_load(configfile)
        self._loaded = True
        logging.info("loaded "+self.configname+" ")

    def __getitem__(self, key):
        if not self._loaded:
            self.load_config()
        return self.cfg.__getitem__(key)

configinstance = Config()

