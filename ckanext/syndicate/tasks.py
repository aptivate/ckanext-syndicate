import logging
import ckanapi

from pylons import config

import ckan.plugins.toolkit as toolkit
from ckan.lib.celery_app import celery
from ckan.lib.helpers import get_pkg_dict_extra

logger = logging.getLogger(__name__)

SYNDICATED_ID_EXTRA = 'syndicated_id'


@celery.task(name='syndicate.sync_package')
def sync_package_task(package, site_url):
    return sync_package(package, site_url)


def get_target():
    ckan_url = config.get('ckan.syndicate.ckan_url')
    api_key = config.get('ckan.syndicate.api_key')
    assert ckan_url and api_key, "Task must have ckan_url and api_key"

    ckan = ckanapi.RemoteCKAN(ckan_url, apikey=api_key)
    return ckan


def sync_package(package_id, site_url):
    logger.info('sync package {0}'.format(package_id))

    # load the package at run of time task (rather than use package state at
    # time of task creation).
    # TODO: what user does the task access CKAN with?
    context={'ignore_auth': True}
    params={
        'id': package_id,
    }
    package = toolkit.get_action(
        'package_show')(
            context,
            params,
        )
    # attempt to get the remote package
    ckan = get_target()

    syndicated_id = get_pkg_dict_extra(package, SYNDICATED_ID_EXTRA)
    name_or_id = syndicated_id if syndicated_id else package['name']

    try:
        remote_package = ckan.action.package_show(id=name_or_id)
    except ckanapi.NotFound:
        logger.info('no syndicated package with id: "%s"' % syndicated_id)
        new_package_data = dict(package)
        del new_package_data['id']
        remote_package = ckan.action.package_create(**new_package_data)

    # set the target package id on the source package
    extras = package['extras']
    # TODO: updating extras
    extras_dict = dict([(o['key'], o['value']) for o in extras])
    extras_dict.update({SYNDICATED_ID_EXTRA: remote_package['id']})
    extras = [{'key': k, 'value': v} for (k, v) in extras_dict.iteritems()]
    package['extras'] = extras

    _update_package_extras(package)


def _update_package_extras(package):
    from ckan import model
    from ckan.lib.dictization.model_save import package_extras_save

    package_id = package['id']
    package_obj = model.Package.get(package_id)
    if not package:
        raise Exception('No Package with ID %s found:s' % package_id)

    extra_dicts = package.get("extras")
    context_ = {'model': model, 'session': model.Session}
    model.repo.new_revision()
    package_extras_save(extra_dicts, package_obj, context_)
    model.Session.commit()
    model.Session.flush()

    _update_search_index(package_obj.id, logger)


def _update_search_index(package_id, log):
    '''
    Tells CKAN to update its search index for a given package.
    '''
    from ckan import model
    from ckan.lib.search.index import PackageSearchIndex
    package_index = PackageSearchIndex()
    context_ = {'model': model, 'ignore_auth': True, 'session': model.Session,
                'use_cache': False, 'validate': False}
    package = toolkit.get_action('package_show')(context_, {'id': package_id})
    package_index.index_package(package, defer_commit=False)
    log.info('Search indexed %s', package['name'])



