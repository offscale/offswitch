#!/usr/bin/env python

import logging
import yaml

from logging.config import dictConfig as _dictConfig

from os import path

__author__ = 'Samuel Marks'
__version__ = '0.0.5-alpha'


def _get_logger():
    with open(path.join(path.dirname(__file__), '_data', 'logging.yml'), 'rt') as f:
        data = yaml.load(f)
    _dictConfig(data)
    return logging.getLogger()


logger = _get_logger()
