#!/usr/bin/env python3

import yaml
import logging


class Config(dict):
    "provides access to config settings"
    CONFIGNAME = "config.yml"

    def __init__(self):
        "read config from file"
        try:
            with open(self.CONFIGNAME, 'r') as configfile:
                self.update(yaml.safe_load(configfile))
            logging.info("loaded " + self.CONFIGNAME)
        except:
            logging.error("failed to load " + self.CONFIGNAME)


CONFIGINSTANCE = Config()
