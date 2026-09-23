#!/usr/bin/env python3

"""Small helpers that were removed from the stdlib or are otherwise handy."""

def strtobool(val: str) -> bool:
    "distutils.util.strtobool replacement (distutils is gone in python 3.12)."
    val = val.lower()
    if val in ('y', 'yes', 't', 'true', 'on', '1'):
        return True
    if val in ('n', 'no', 'f', 'false', 'off', '0'):
        return False
    raise ValueError("invalid truth value %r" % (val,))