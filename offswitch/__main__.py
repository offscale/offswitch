# -*- coding: utf-8 -*-
from argparse import ArgumentParser
from functools import partial
from os import path

from pkg_resources import resource_filename

from offswitch import __version__

from .destroy import destroy

config_join = partial(path.join, path.dirname(__file__), "config")


def _build_parser():
    """
    CLI parser builder using builtin `argparse` module

    :return: instanceof ArgumentParser
    :rtype: ```ArgumentParser```
    """
    parser = ArgumentParser(description="Destroy compute nodes")
    parser.add_argument(
        "-s",
        "--strategy",
        help="strategy file [providers.sample.json]",
        default=resource_filename("offswitch.config", "providers.sample.json"),
    )
    parser.add_argument(
        "-p",
        "--provider",
        help="Only switch off this provider. Can be specified repetitively.",
        action="append",
    )
    parser.add_argument(
        "-d",
        "--delete",
        help="Only switch off this name. Can be specified repetitively.",
        action="append",
    )
    parser.add_argument(
        "--version", action="version", version="%(prog)s {}".format(__version__)
    )
    return parser


if __name__ == "__main__":
    args = _build_parser().parse_args()
    destroy(args.strategy, args.provider, args.delete)
