from os import environ
from json import loads
from itertools import imap, ifilter, chain, groupby
from sys import stderr
from urlparse import urlparse
from collections import namedtuple
from operator import itemgetter

from libcloud import security
from libcloud.common.softlayer import SoftLayerException
from libcloud.common.types import InvalidCredsError, LibcloudError
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver

from etcd import Client

from offconf import replace_variables
from offutils import flatten, it_consumes, pp, raise_f
from offutils_strategy_register import node_to_dict, dict_to_node

from __init__ import logger

if environ.get('enable_ssl', False):
    security.VERIFY_SSL_CERT = True
elif environ.get('disable_ssl'):
    security.VERIFY_SSL_CERT = False


def destroy(config_filename, restrict_provider_to=None, delete_only=None):
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
                                        (lambda provider_cls: provider_cls(region=provider_dict['provider']['region'],
                                                                           **provider_dict['auth'])
                                        if 'region' in provider_dict['provider'] else provider_cls(
                                            **provider_dict['provider'])
                                         )(get_driver(
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
    provider2nodes = {}
    for provider, driver in provider2conf_and_driver.iteritems():
        try:
            provider2nodes[provider] = tuple(
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
        except (InvalidCredsError, AttributeError) as e:
            logger.exception(e)

    print 'provider2nodes'
    pp(provider2nodes)

    uuid2keys = {}
    name2node = {}
    key2locs = {}
    for key in flatten(etcd_ls(client)):
        if (lambda v: isinstance(v, basestring) and v.startswith('{'))(client.get(key).value):
            name = key.rpartition('/')[2]
            node_d = loads(client.get(key).value)  # TODO: Only call `client.get` once per `key`
            uuid = node_d['uuid']

            if uuid in uuid2keys:
                uuid2keys[uuid].add(key)
                key2locs[name].add(key)
            else:
                uuid2keys[uuid] = {key}
                key2locs[name] = {key}
                # TODO: Fix missing _class on vagrant
                '''print 'node_d'
                pp(node_d)
                name2node[name] = dict_to_node(dict(_class=node_d['driver'],
                                                    driver_cls=node_d['driver'],
                                                    **node_d))'''
                name2node[name] = node_d

    '''print 'uuid2key'
    pp(uuid2keys)
    print 'key2locs'
    pp(key2locs)
    print 'name2node'
    pp(name2node)'''
    if delete_only:
        for name in delete_only:
            try:
                for key in key2locs[name]:
                    client.delete(key)
                    logger.info('rm {!s}'.format(key))
            except KeyError as e:
                logger.error('"{!s}" not found'.format(e.message))
        remove_empty_dirs(client)
        exit()

    exit(1)
    # Filter to just ones inside etcd
    within_etcd = {
        provider: imap(lambda n: rm_prov_etcd(client, n.node), nodes)
        for provider, nodes in provider2nodes.iteritems()
        for node in nodes
        if node.uuid in uuid2keys
        }
    print 'within_etcd'
    pp(within_etcd)

    # deprovision and delete from etcd
    for provider, dl_op_iter in within_etcd.iteritems():
        logger.info('Deleting from {provider}'.format(provider=provider))

        try:
            within_etcd[provider] = tuple(dl_op_iter)
            print 'within_etcd[provider] =', within_etcd[provider]
        except LibcloudError as e:
            print 'e.message {!r}'.format(e.message)
            (isinstance(e, SoftLayerException)
             and e.message == 'SoftLayer_Exception_NotFound: A billing item is required to process a cancellation.'
             and (logger.exception(e) or True)) or raise_f(e)

    print 'within_etcd =', within_etcd
    # Delete all empty etcd directories.

    remove_empty_dirs(client)

    return client


def remove_empty_dirs(client):
    for i in xrange(20):  # TODO: walk the tree rather than hackily rerun
        it_consumes(
            logger.info('rmdir {directory}'.format(directory=directory, res=client.delete(directory, dir=True)))
            for directory in flatten(etcd_empty_dirs(client))
        )


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
    return filter(lambda key: isinstance(key, basestring) and key.encode('utf-8').endswith(node_name),
                  tuple(chain(*etcd_ls(client, directory=directory))))


to_driver_obj = lambda provider: (lambda provider_name: get_driver(
    getattr(Provider, provider_name)
)(*provider['auth'].values()))(provider['provider']['name'])
