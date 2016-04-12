from os import name as os_name, environ
from json import loads
from itertools import imap, chain, groupby
from urlparse import urlparse

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

    driver_names = {
        driver_name.upper(): driver_tuple[1] for driver_name, driver_tuple in DRIVERS.iteritems()
        for provider in providers
        if driver_tuple[1].upper().startswith(provider['provider']['name'])}

    # Map nodes to their provider, including ones outside etcd
    provider2nodes = {
        key: tuple(val) for key, val in {
        k: v for k, v in groupby(
        (
            node for node in (loads(client.get(j).value)
                              for c in etcd_ls(client) for j in c)
            if node['state'] == 'running'
        ), lambda x: x['driver'])
        if next((True for val in driver_names.itervalues() if val == k), None)
        }.iteritems()}

    # Filter to just ones we have auth details for
    filtered_providers = (provider for provider in providers
                          if driver_names[provider['provider']['name']] in provider2nodes)

    # Filter to just ones inside etcd; then deprovision and delete from etcd
    logger.info('Dropped: {}'.format(
        {
            provider['provider']['name']: rm_prov_etcd(client, n)
            for provider in filtered_providers
            for n in to_driver_obj(provider).list_nodes()
            if next((n.uuid == node['uuid']
                     for node in provider2nodes[driver_names[provider['provider']['name']]]), None)
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
