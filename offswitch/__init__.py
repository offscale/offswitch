#!/usr/bin/env python

import logging
from logging.config import dictConfig as _dictConfig
from os import path

import yaml

__author__ = "Samuel Marks"
__version__ = "0.0.10-alpha1"
__description__ = "Configuration based deprovisioning tool with Apache Libcloud"


def get_logger(name=None):
    """
    Create logger—with optional name—with the logging.yml config

    :param name: Optional name of logger
    :type name: ```Optional[str]```

    :return: instanceof Logger
    :rtype: ```Logger```
    """
    with open(path.join(path.dirname(__file__), "_data", "logging.yml"), "rt") as f:
        data = yaml.safe_load(f)
    _dictConfig(data)
    return logging.getLogger(name=name)


logger = get_logger()
