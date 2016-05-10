from os import environ
from json import loads
from itertools import imap, ifilter, chain
from urlparse import urlparse
from collections import namedtuple
from operator import itemgetter

from libcloud import security
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver

from etcd import Client

from offconf import replace_variables
from offutils import flatten, it_consumes, pp

from __init__ import logger

if environ.get('enable_ssl', False):
    security.VERIFY_SSL_CERT = True
elif environ.get('disable_ssl'):
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
                                    namedtuple('_', 'conf driver_cls')(
                                        provider_dict,
                                        (lambda provider_cls: provider_cls(
                                            region=provider_dict['provider']['region'],
                                            **provider_dict['auth']
                                        ))(get_driver(
                                            getattr(Provider, provider_dict['provider']['name'])
                                            if hasattr(Provider, provider_dict['provider']['name'])
                                            else itemgetter(1)(next(ifilter(
                                                lambda (prov_name, value): value == provider_dict['provider'][
                                                    'name'].lower(),
                                                imap(lambda prov_name: (prov_name, getattr(Provider, prov_name)),
                                                     dir(Provider))
                                            )))
                                        )))), providers)
    )

    # Map nodes to their provider, including ones outside etcd
    provider2nodes = {
        provider: tuple(
            namedtuple('_', 'uuid node')(node.uuid, node) for node in
            driver.driver_cls.list_nodes(*((driver.conf['create_with']['ex_cloud_service_name'],)
                                           if driver.conf['provider']['name'] == 'AZURE'
                                           else tuple()
                                           ))
            if driver.driver_cls.NODE_STATE_MAP and node.state in (
                driver.driver_cls.NODE_STATE_MAP.get(
                    'running',
                    next((node.state for k, v in driver.driver_cls.NODE_STATE_MAP.iteritems()
                          if 'running' in v), None)
                ),
                driver.driver_cls.NODE_STATE_MAP.get('active')
            ) or not driver.driver_cls.NODE_STATE_MAP and node.state in ('running',)
        )
        for provider, driver in provider2conf_and_driver.iteritems()}

    uuid2key = {loads(client.get(key).value)['uuid']: key
                for directory in etcd_ls(client)
                for key in directory
                if isinstance(key, basestring)}

    # Filter to just ones inside etcd; then deprovision and delete from etcd
    logger.info('Dropped: {}'.format(
        {
            provider: tuple(imap(lambda n: rm_prov_etcd(client, n.node), nodes))
            for provider, nodes in provider2nodes.iteritems()
            for node in nodes
            if node.uuid in uuid2key
            }
    ))

    # Delete all empty etcd directories.
    for i in xrange(20):  # TODO: walk the tree rather than hackily rerun
        it_consumes(
            logger.info('rmdir {directory}'.format(directory=directory, res=client.delete(directory, dir=True)))
            for directory in flatten(etcd_empty_dirs(client))
        )

    return client


def rm_prov_etcd(client, node):
    return tuple(chain(*(tuple(imap(lambda name: (lambda res: 'etcd::deleted')(client.delete(name)),
                                    etcd_filter(client, node.name))),
                         (lambda res: ('provider::destroyed',))(node.destroy()))))


def etcd_ls(client, directory='/'):
    return tuple(imap(lambda child: etcd_ls(client, child['key']) if child.get('dir') else child['key'],
                      client.get(directory)._children))


def etcd_empty_dirs(client, directory='/'):
    return (
        child['key'] if not client.get(child['key'])._children else etcd_empty_dirs(client, child['key'])
        for child in client.get(directory)._children
        if child.get('dir')
    )


def etcd_filter(client, node_name, directory='/'):
    return filter(lambda key: key.encode('utf-8').endswith(node_name),
                  tuple(chain(*etcd_ls(client, directory=directory))))


to_driver_obj = lambda provider: (lambda provider_name: get_driver(
    getattr(Provider, provider_name)
)(*provider['auth'].values()))(provider['provider']['name'])
