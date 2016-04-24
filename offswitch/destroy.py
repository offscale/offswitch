from os import name as os_name, environ
from json import loads
from itertools import imap, chain
from urlparse import urlparse
from collections import namedtuple

from libcloud import security
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver, DRIVERS

from etcd import Client

from offconf import replace_variables

from __init__ import logger

if environ.get('enable_ssl', False):
    security.VERIFY_SSL_CERT = True
elif os_name == 'nt' or environ.get('disable_ssl'):
    # AWS Certificates are acting up (on Windows), remove this in production:
    security.VERIFY_SSL_CERT = False


def destroy(config_filename, restrict_provider_to=None):
    with open(config_filename, 'rt') as f:
        config_contents = f.read()

    config_dict = loads(replace_variables(config_contents))
    del config_contents

    providers = tuple(obj for obj in config_dict['provider']['options']
                      if obj['provider']['name'] in restrict_provider_to
                      or obj['provider']['name'] == restrict_provider_to) if restrict_provider_to \
        else tuple(obj for obj in config_dict['provider']['options'])

    client = (lambda etcd_server_location: Client(
        protocol=etcd_server_location.scheme,
        host=etcd_server_location.hostname,
        port=etcd_server_location.port
    ))(urlparse(config_dict['etcd_server']))

    provider2conf_and_driver = dict(
        imap(lambda provider_dict: (provider_dict['provider']['name'],
                                    namedtuple('_', 'dict driver')(provider_dict, (lambda provider_cls: provider_cls(
                                        subscription_id=provider_dict['auth']['subscription_id'],
                                        key_file=provider_dict['auth']['key_file']
                                    ) if provider_dict['provider']['name'] == 'AZURE' else provider_cls(
                                        provider_dict['auth']['username'],
                                        provider_dict['auth']['key'],
                                        region=provider_dict['provider']['region']
                                    ))(get_driver(getattr(Provider, provider_dict['provider']['name']))))), providers)
    )

    # Map nodes to their provider, including ones outside etcd
    provider2nodes = {
        provider: tuple(
            namedtuple('_', 'uuid node')(node.uuid, node) for node in
            driver.driver.list_nodes(*(tuple() if not driver.dict['provider'].get('cloud_name')
                                       else (driver.dict['provider']['cloud_name'],)))
            if node.state in (driver.driver.NODE_STATE_MAP['pending'],
                              driver.driver.NODE_STATE_MAP['running']))
        for provider, driver in provider2conf_and_driver.iteritems()}

    uuid2key = {loads(client.get(key).value)['uuid']: key
                for directory in etcd_ls(client)
                for key in directory}

    # Filter to just ones inside etcd; then deprovision and delete from etcd
    logger.info('Dropped: {}'.format(
        {
            provider: tuple(imap(lambda n: rm_prov_etcd(client, n.node), nodes))
            for provider, nodes in provider2nodes.iteritems()
            for node in nodes
            if node.uuid in uuid2key
            }
    ))

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
)(*provider['auth'].values()))(provider['provider']['name'])

destroy_nodes = lambda client, driver_obj, cloud_name=environ.get('AZURE_CLOUD_NAME'): tuple(
    {node.name: rm_prov_etcd(client, node)}
    for node in driver_obj.list_nodes(
        *(tuple() if not cloud_name else (cloud_name,))
    )
)
