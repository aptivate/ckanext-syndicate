import json
import logging

import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
from ckan.lib.helpers import asbool
from routes.mapper import SubMapper

from pylons import config
import ckan.model as model
from sqlalchemy.orm.exc import NoResultFound
from ckan.model.domain_object import DomainObjectOperation
from ckanext.syndicate.syndicate_model.syndicate_config import SyndicateConfig
import ckanext.syndicate.actions as actions

syndicate_dataset = actions._syndicate_dataset

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def _convert_from_json(value):
    if value is not toolkit.missing:
        try:
            value = json.loads(value)
        except ValueError:
            logger.error(
                "Error during unserializing json in validator", exc_info=True)
    return value


def _convert_to_json(value):
    return json.dumps(value)


def _get_syndicate_endpoints():
    return [
        profile['syndicate_url']
        for profile in _get_syndicate_profiles()]


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


def _get_syndicate_profiles():
    profiles_list = []
    profiles = model.Session.query(SyndicateConfig).all()

    for profile in profiles:
        profiles_list.append(actions._prepare_profile_dict(profile))

    return profiles_list


def _get_syndicate_profile(syndicate_url):
    profile_dict = {}

    try:
        profile = model.Session.query(SyndicateConfig).filter(
            SyndicateConfig.syndicate_url == syndicate_url).one()
        profile_dict = actions._prepare_profile_dict(profile)
    except NoResultFound:
        pass

    return profile_dict


class SyndicatePlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.IDomainObjectModification, inherit=True)
    plugins.implements(plugins.IRoutes, inherit=True)
    plugins.implements(plugins.IValidators)
    plugins.implements(plugins.ITemplateHelpers)
    plugins.implements(plugins.IActions)

    # IActions

    def get_actions(self):
        return dict(
            syndicate_individual_dataset=actions.syndicate_individual_dataset,
            syndicate_datasets_by_endpoint=actions.syndicate_datasets_by_endpoint
        )

    # ITemplateHelpers

    def get_helpers(self):
        return dict(
            get_syndicate_endpoints=_get_syndicate_endpoints
        )

    # IValidators

    def get_validators(self):
        return dict(
            convert_from_json=_convert_from_json,
            convert_to_json=_convert_to_json
        )

    # IConfigurer

    def update_config(self, config_):
        toolkit.add_template_directory(config_, 'templates')
        toolkit.add_public_directory(config_, 'public')
        toolkit.add_resource('fanstatic', 'syndicate')

    # Based on ckanext-webhooks plugin
    # IDomainObjectNotification & IResourceURLChange
    def notify(self, entity, operation=None):
        if not operation:
            # This happens on IResourceURLChange
            return

        if isinstance(entity, model.Package):
            self._syndicate_dataset(entity, operation)

    def _syndicate_dataset(self, dataset, operation):
        topic = self._get_topic('dataset', operation)
        if topic is None:
            return

        # Get syndication profiles from db
        syndicate_profiles = _get_syndicate_profiles()

        if syndicate_profiles:
            for profile in syndicate_profiles:
                str_endpoints = dataset.extras.get(u'syndication_endpoints', u'[]')
                try:
                    endpoints = json.loads(str_endpoints)
                except ValueError:
                    logger.error((
                        'Failed to unserialize '
                        'syndication endpoints of <{}>'
                    ).format(dataset.id), exc_info=True)
                    endpoints = []

                if endpoints and profile['syndicate_url'] not in endpoints:
                    logger.debug('Skip endpoint {} for <{}>'.format(
                        profile['syndicate_url'], dataset.id))
                    continue

                if self._syndicate(dataset, profile['syndicate_flag']):
                    logger.debug("Syndicate <{}> to {}".format(
                        dataset.id, profile['syndicate_url']))
                    syndicate_dataset(dataset.id, topic, profile)
                else:
                    continue
        else:
            if self._syndicate(dataset):
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
        syndicate_ctrl = "ckanext.syndicate.controllers.syndicate:SyndicateController"
        with SubMapper(
            map,
            controller=syndicate_ctrl,
            path_prefix=''
        ) as m:
            m.connect(
                'syndicate_sysadmin_ui', '/syndicate-config',
                action='syndicate_config')
            m.connect(
                'syndicate_global_logs', '/syndicate-global-logs',
                action='syndicate_global_logs')

        # Syndicate organizations page
        with SubMapper(
            map, controller=syndicate_ctrl, path_prefix='/organization'
        ) as m:
            m.connect(
                'syndicate_logs', '/syndicate-logs/{id}', action='tasks_list')

        with SubMapper(
            map, controller=syndicate_ctrl, path_prefix='/dataset/syndicate'
        ) as m:
            m.connect(
                'syndicate_logs_dataset', '/{id}/syndicate-logs',
                action='tasks_list_dataset')

        with SubMapper(
            map, controller=syndicate_ctrl, path_prefix='/syndicate-logs'
        ) as m:
            # Ajax syndicate log remove
            m.connect(
                'syndicate_log_remove', '/syndicate-log-remove',
                action='syndicate_log_remove')
            # Ajax syndicate log retry
            m.connect(
                'syndicate_log_remove', '/syndicate-log-retry',
                action='syndicate_log_retry')

        return map


class SyndicateDatasetPlugin(
        plugins.SingletonPlugin, toolkit.DefaultDatasetForm):
    plugins.implements(plugins.IDatasetForm)

    # IDatasetForm

    def is_fallback(self):
        return True

    def package_types(self):
        return []

    def _modify_package_schema(self, schema):
        schema.update({
            'syndication_endpoints': [
                toolkit.get_validator('ignore_missing'),
                toolkit.get_converter('convert_to_list_if_string'),
                toolkit.get_converter('convert_to_json'),
                toolkit.get_converter('convert_to_extras')
            ]
        })
        return schema

    def create_package_schema(self):
        schema = super(SyndicateDatasetPlugin, self).create_package_schema()
        schema = self._modify_package_schema(schema)
        return schema

    def update_package_schema(self):
        schema = super(SyndicateDatasetPlugin, self).update_package_schema()
        schema = self._modify_package_schema(schema)
        return schema

    def show_package_schema(self):
        schema = super(SyndicateDatasetPlugin, self).show_package_schema()
        schema.update({
            'syndication_endpoints': [
                toolkit.get_converter('convert_from_extras'),
                toolkit.get_converter('convert_from_json'),
                toolkit.get_validator('ignore_missing')]
        })
        return schema
