from os import path
from functools import partial
from argparse import ArgumentParser
from pkg_resources import resource_filename

from destroy import destroy

config_join = partial(path.join, path.dirname(__file__), 'config')


def _build_parser():
    parser = ArgumentParser(description='Destroy compute nodes')
    parser.add_argument('-s', '--strategy', help='strategy file [strategy.sample.json]',
                        default=resource_filename('offswitch.config', 'providers.sample.json'))
    parser.add_argument('-p', '--provider', help='Only switch off this provider. Can be specified repetitively.',
                        action='append')
    return parser


if __name__ == '__main__':
    args = _build_parser().parse_args()
    destroy(args.strategy, args.provider)
