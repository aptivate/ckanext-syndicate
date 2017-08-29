import os

import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
from ckan.lib.celery_app import celery
from ckan.lib.helpers import asbool
from routes.mapper import SubMapper

from pylons import config
import ckan.model as model
from sqlalchemy.orm.exc import NoResultFound
from ckan.model.domain_object import DomainObjectOperation
from ckanext.syndicate.syndicate_model.syndicate_config import SyndicateConfig

import uuid


def get_syndicate_flag():
    return config.get('ckan.syndicate.flag', 'syndicate')


def get_syndicated_id():
    return config.get('ckan.syndicate.id', 'syndicated_id')


def get_syndicated_author():
    return config.get('ckan.syndicate.author')


def get_syndicated_name_prefix():
    return config.get('ckan.syndicate.name_prefix', '')


def get_syndicated_organization():
    return config.get('ckan.syndicate.organization', None)


def is_organization_preserved():
    return asbool(config.get('ckan.syndicate.replicate_organization', False))

def _prepare_profile_dict(profile):
    profile_dict = {
            'id': profile.id,
            'syndicate_url': profile.syndicate_url,
            'syndicate_api_key': profile.syndicate_api_key,
            'syndicate_organization': profile.syndicate_organization,
            'syndicate_flag': profile.syndicate_flag,
            'syndicate_field_id': profile.syndicate_field_id,
            'syndicate_prefix': profile.syndicate_prefix,
            'syndicate_replicate_organization': profile.syndicate_replicate_organization,
            'syndicate_author': profile.syndicate_author
        }
    
    return profile_dict

def _get_syndicate_profiles():
    profiles_list = []
    profiles = model.Session.query(SyndicateConfig).all()

    for profile in profiles:
        profiles_list.append(_prepare_profile_dict(profile))

    return profiles_list

def _get_syndicate_profile(syndicate_url):
    profile_dict = {}

    try:
        profile = model.Session.query(SyndicateConfig).filter(
            SyndicateConfig.syndicate_url == syndicate_url).one()
        profile_dict = _prepare_profile_dict(profile)
    except NoResultFound:
        pass

    return profile_dict

def syndicate_dataset(package_id, topic, profile=None):
    ckan_ini_filepath = os.path.abspath(config['__file__'])
    celery.send_task(
        'syndicate.sync_package',
        args=[package_id, topic, ckan_ini_filepath, profile],
        task_id='{}-{}'.format(str(uuid.uuid4()), package_id)
    )


class SyndicatePlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.IDomainObjectModification, inherit=True)
    plugins.implements(plugins.IRoutes, inherit=True)

    # IConfigurer

    def update_config(self, config_):
        toolkit.add_template_directory(config_, 'templates')
        toolkit.add_public_directory(config_, 'public')
        toolkit.add_resource('fanstatic', 'syndicate')

    ## Based on ckanext-webhooks plugin
    # IDomainObjectNotification & IResourceURLChange
    def notify(self, entity, operation=None):
        if not operation:
            # This happens on IResourceURLChange
            return

        if isinstance(entity, model.Package):
            self._syndicate_dataset(entity, operation)

    def _syndicate_dataset(self, dataset, operation):
        topic = self._get_topic('dataset', operation)

        # Get syndication profiles from db
        syndicate_profiles = _get_syndicate_profiles()

        if syndicate_profiles:
            for profile in syndicate_profiles:
                if topic is not None and self._syndicate(dataset, profile['syndicate_flag']):
                    syndicate_dataset(dataset.id, topic, profile)
                else:
                    continue
        else:
            if topic is not None and self._syndicate(dataset):
                syndicate_dataset(dataset.id, topic)

    def _syndicate(self, dataset, syndicate_flag=None):

        if syndicate_flag:
            return (not dataset.private and
                    asbool(dataset.extras.get(syndicate_flag, 'false')))
        else:
            return (not dataset.private and
                    asbool(dataset.extras.get(get_syndicate_flag(), 'false')))

    def _get_topic(self, prefix, operation):
        topics = {
            DomainObjectOperation.new: 'create',
            DomainObjectOperation.changed: 'update',
        }

        topic = topics.get(operation, None)

        if topic is not None:
            return '{0}/{1}'.format(prefix, topic)

        return None

    # IRouter

    def before_map(self, map):

        # Syndicate UI
        # Sundicate Sysadmin configs page
        with SubMapper(
            map,
            controller="ckanext.syndicate.controllers.syndicate:SyndicateController",
            path_prefix=''
        ) as m:
            m.connect('syndicate_sysadmin_ui', '/syndicate-config', action='syndicate_config')
            m.connect('syndicate_global_logs', '/syndicate-global-logs', action='syndicate_global_logs')
            # Sundicate Sysadmin configs remove config item
            # m.connect('syndicate_config_remove', '/syndicate-config/remove', action='syndicate_config_remove')
        
        # Syndicate organizations page
        with SubMapper(
            map,
            controller="ckanext.syndicate.controllers.syndicate:SyndicateController",
            path_prefix='/organization'
        ) as m:
            m.connect('syndicate_logs', '/syndicate-logs/{id}', action='tasks_list')

        with SubMapper(
            map,
            controller="ckanext.syndicate.controllers.syndicate:SyndicateController",
            path_prefix='/syndicate-logs'
        ) as m:
            # Ajax syndicate log remove
            m.connect('syndicate_log_remove', '/syndicate-log-remove', action='syndicate_log_remove')
            # Ajax syndicate log retry
            m.connect('syndicate_log_remove', '/syndicate-log-retry', action='syndicate_log_retry')


        return map
