import logging
from urlparse import urlparse
import ckanapi
import os
import routes

from pylons import config

import ckan.plugins.toolkit as toolkit
from ckan.lib.celery_app import celery
from ckan.lib.helpers import get_pkg_dict_extra
from ckanext.syndicate.plugin import (
    get_syndicate_flag,
    get_syndicated_id,
    get_syndicated_name_prefix,
    get_syndicated_organization,
    get_syndicated_author,
    is_organization_preserved,
)
import ckan.plugins as plugins

from ckanext.syndicate.interfaces import ISyndication

logger = logging.getLogger(__name__)

try:
    from ckan.lib.celery_app import celery

    @celery.task(name='syndicate.sync_package')
    def sync_package_task_celery(*args, **kwargs):
        return sync_package_task(*args, **kwargs)
except ImportError:
    pass


def sync_package_task(
    package, action, ckan_ini_filepath, syndicate_profile=None):
    logger = sync_package_task.get_logger()
    load_config(ckan_ini_filepath)
    register_translator()
    logger.info("Sync package %s, with action %s" % (package, action))
    return sync_package(package, action, None, syndicate_profile)


# TODO: why mp this
# enable celery logging for when you run nosetests -s
log = logging.getLogger('ckanext.syndicate.tasks')


def get_logger():
    return log


sync_package_task.get_logger = get_logger


def load_config(ckan_ini_filepath):
    import paste.deploy
    config_abs_path = os.path.abspath(ckan_ini_filepath)
    conf = paste.deploy.appconfig('config:' + config_abs_path)
    import ckan
    ckan.config.environment.load_environment(conf.global_conf,
                                             conf.local_conf)

    # give routes enough information to run url_for
    parsed = urlparse(conf.get('ckan.site_url', 'http://0.0.0.0'))
    request_config = routes.request_config()
    request_config.host = parsed.netloc + parsed.path
    request_config.protocol = parsed.scheme


def register_translator():
    # https://github.com/ckan/ckanext-archiver/blob/master/ckanext/archiver/bin/common.py
    # If not set (in cli access), patch the a translator with a mock, so the
    # _() functions in logic layer don't cause failure.
    from paste.registry import Registry
    from pylons import translator
    from ckan.lib.cli import MockTranslator
    if 'registery' not in globals():
        global registry
        registry = Registry()
        registry.prepare()

    if 'translator_obj' not in globals():
        global translator_obj
        translator_obj = MockTranslator()
        registry.register(translator, translator_obj)


def get_target(profile=None):
    if hasattr(get_target, 'ckan'):
        return get_target.ckan
    ckan_url = profile[
        'syndicate_ckan_url'] if profile else config.get(
            'ckan.syndicate.ckan_url')
    api_key = profile[
        'syndicate_api_key'] if profile else config.get(
            'ckan.syndicate.api_key')
    user_agent = config.get('ckan.syndicate.user_agent', None)
    assert ckan_url and api_key, "Task must have ckan_url and api_key"

    ckan = ckanapi.RemoteCKAN(ckan_url, apikey=api_key, user_agent=user_agent)

    get_target.ckan = ckan
    return ckan


def filter_extras(extras, profile=None):
    syndicate_flag = profile.get(
        'syndicate_flag', 'syndicate') if profile else get_syndicate_flag()
    extras_dict = dict([(o['key'], o['value']) for o in extras])
    extras_dict.pop(syndicate_flag, None)
    return [{'key': k, 'value': v} for (k, v) in extras_dict.iteritems()]


def filter_resources(resources):
    return [
        {'url': r['url'], 'name': r['name']} for r in resources
    ]


def sync_package(package_id, action, ckan_ini_filepath=None, profile=None):
    logger.info('sync package {0}'.format(package_id))

    # load the package at run of time task (rather than use package state at
    # time of task creation).
    from ckan import model
    context = {'model': model, 'ignore_auth': True, 'session': model.Session,
               'use_cache': False, 'validate': False}

    params = {
        'id': package_id,
    }
    package = toolkit.get_action('package_show')(
        context,
        params,
    )
    if action == 'dataset/create':
        logger.info("In create package stage")
        _create_package(package, profile)

    elif action == 'dataset/update':
        logger.info("In update package stage")
        _update_package(package, profile)
    else:
        raise Exception('Unsupported action {0}'.format(action))


def replicate_remote_organization(org, profile=None):
    ckan = get_target(profile)

    try:
        remote_org = ckan.action.organization_show(id=org['name'])
    except toolkit.ObjectNotFound:
        org.pop('image_url')
        org.pop('id')
        remote_org = ckan.action.organization_create(**org)

    return remote_org['id']


def _create_package(package, profile=None):
    syndicate_name_prefix = profile[
        'syndicate_name_prefix'] if profile else get_syndicated_name_prefix()
    syndicate_replicate_org = profile.get(
        'syndicate_replicate_organization',
        False) if profile else is_organization_preserved()
    syndicate_org = profile.get(
        'syndicate_organization',
        None) if profile else get_syndicated_organization()
    syndicate_author = profile[
        'syndicate_author'] if profile else get_syndicated_author()

    ckan = get_target(profile)
    # Create a new package based on the local instance
    new_package_data = dict(package)
    del new_package_data['id']

    new_package_data['name'] = new_package_data['name']

    if syndicate_name_prefix:
        new_package_data['name'] = "{prefix}-{name}".format(
            prefix=syndicate_name_prefix,
            name=new_package_data['name'])

    new_package_data['extras'] = filter_extras(
        new_package_data['extras'], profile)
    new_package_data['resources'] = filter_resources(
        package['resources'])

    org = new_package_data.pop('organization')

    if syndicate_replicate_org:
        logger.info("Replicating Organization for Dataset")
        org_id = replicate_remote_organization(org, profile)
    else:
        logger.info("Syndicating into {org} Organization.".format(
            org=syndicate_org))
        org_id = syndicate_org

    new_package_data['owner_org'] = org_id

    # TODO: No automated test
    for plugin in plugins.PluginImplementations(ISyndication):
        plugin.before_syndication_create(new_package_data, package['id'])

    try:
        logger.info("Creating Dataset '{0}'".format(new_package_data['name']))
        remote_package = ckan.action.package_create(**new_package_data)
        set_syndicated_id(package, remote_package['id'], profile)
    except toolkit.ValidationError as e:
        if 'That URL is already in use.' in e.error_dict.get('name', []):
            logger.info((
                "package with name '{0}' "
                "already exists. Check creator.").format(
                new_package_data['name'])
            )
            author = syndicate_author
            if author is None:
                raise
            try:
                remote_package = ckan.action.package_show(
                    id=new_package_data['name'])
                remote_user = ckan.action.user_show(id=author)
            except toolkit.ValidationError as e:
                log.error(e.errors)
                raise
            except toolkit.ObjectNotFound as e:
                log.error('User "{0}" not found'.format(author))
                raise
            else:
                if remote_package['creator_user_id'] == remote_user['id']:
                    logger.info("Author is the same({0}). Updating".format(
                        author))
                    ckan.action.package_update(
                        id=remote_package['id'],
                        **new_package_data
                    )
                    set_syndicated_id(package, remote_package['id'], profile)
                else:
                    logger.info(
                        ("Creator of remote package '{0}' "
                            "did not match '{1}'. Skipping").format(
                            remote_user['name'], author))


def _update_package(package, profile=None):
    syndicate_org = profile.get(
        'syndicate_organization',
        None) if profile else get_syndicated_organization()
    syndicate_replicate_org = profile.get(
        'syndicate_replicate_organization',
        False) if profile else is_organization_preserved()
    syndicate_id = profile.get(
        'syndicate_field_id',
        'syndicated_id') if profile else get_syndicated_id()

    syndicated_id = get_pkg_dict_extra(package, syndicate_id)

    if syndicated_id is None:
        logger.info("Syndicated ID is missing, heading to package create")
        _create_package(package, profile)
        return

    ckan = get_target(profile)

    try:
        updated_package = dict(package)
        # Keep the existing remote ID and Name
        del updated_package['id']
        del updated_package['name']

        updated_package['extras'] = filter_extras(
            package['extras'], profile)
        updated_package['resources'] = filter_resources(
            package['resources'])

        org = updated_package.pop('organization')

        if syndicate_replicate_org:
            logger.info("Replicating Organization for Dataset")
            org_id = replicate_remote_organization(org, profile)
        else:
            logger.info("Syndicating into {org} Organization.".format(
                org=syndicate_org))
            org_id = syndicate_org

        updated_package['owner_org'] = org_id

        # TODO: No automated test
        for plugin in plugins.PluginImplementations(ISyndication):
            plugin.before_syndication_update(updated_package, package['id'])

        logger.info("Updating Dataset {0}".format(syndicated_id))
        ckan.action.package_update(
            id=syndicated_id,
            **updated_package
        )
    except ckanapi.NotFound:
        _create_package(package, profile)


def set_syndicated_id(local_package, remote_package_id, profile=None):
    """ Set the remote package id on the local package """
    syndicate_id = profile.get(
        'syndicate_field_id',
        'syndicated_id') if profile else get_syndicated_id()
    extras = local_package['extras']
    extras_dict = dict([(o['key'], o['value']) for o in extras])
    extras_dict.update({syndicate_id: remote_package_id})
    extras = [{'key': k, 'value': v} for (k, v) in extras_dict.iteritems()]
    local_package['extras'] = extras
    _update_package_extras(local_package)


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
