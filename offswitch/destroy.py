from json import loads
from itertools import ifilter, imap, chain
from urlparse import urlparse

from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver

from etcd import Client

from offconf import replace_variables
from offutils import pp

from __init__ import logger


def destroy(config_filename):
    with open(config_filename, 'rt') as f:
        config = replace_variables(f.read())
    config = loads(config)

    client = (lambda etcd_server_location: Client(
        protocol=etcd_server_location.scheme, host=etcd_server_location.hostname, port=etcd_server_location.port
    ))(urlparse(config['etcd_server']))
    logger.info(
        'Dropping from provider: {}'.format(
            tuple(chain(*tuple(imap(lambda provider: destroy_nodes(client, to_driver_obj(provider)),
                                    config['provider']['options']))))
        )
    )
    return client


def rm_prov_etcd(client, node):
    return tuple(chain(*(tuple(imap(lambda name: (lambda res: 'etcd::deleted')(client.delete(name)),
                                    etcd_filter(client, node.name))),
                         (lambda res: ('provider::destroyed',))(node.destroy()))))


def etcd_ls(client, directory='/'):
    return tuple(imap(lambda child: etcd_ls(client, child['key']) if child.get('dir') else child['key'],
                      client.get(directory)._children))


def etcd_filter(client, node_name, directory='/'):
    return filter(lambda key: key.encode('utf-8').endswith(node_name),
                  tuple(chain(*etcd_ls(client, directory=directory))))


to_driver_obj = lambda provider: (lambda provider_name: get_driver(
    getattr(Provider, provider_name)
)(*provider[provider_name]['auth'].values()))(provider.keys()[0])

destroy_nodes = lambda client, driver_obj: tuple(
    imap(lambda node: {node.name: rm_prov_etcd(client, node)}, driver_obj.list_nodes())
)
