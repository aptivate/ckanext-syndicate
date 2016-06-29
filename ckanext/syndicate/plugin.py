import os

import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
from ckan.lib.celery_app import celery
from ckan.lib.helpers import asbool

from pylons import config
import ckan.model as model
from ckan.model.domain_object import DomainObjectOperation

import uuid


def get_syndicate_flag():
    return config.get('ckan.syndicate.flag', 'syndicate')


def get_syndicated_id():
    return config.get('ckan.syndicate.id', 'syndicated_id')


def get_syndicated_name_prefix():
    return config.get('ckan.syndicate.name_prefix', '')


def get_syndicated_organization():
    return config.get('ckan.syndicate.organization', None)


def syndicate_dataset(package_id, topic):
    ckan_ini_filepath = os.path.abspath(config['__file__'])
    celery.send_task(
        'syndicate.sync_package',
        args=[package_id, topic, ckan_ini_filepath],
        task_id='{}-{}'.format(str(uuid.uuid4()), package_id)
    )


class SyndicatePlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.IDomainObjectModification, inherit=True)

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

        if topic is not None and self._syndicate(dataset):
            syndicate_dataset(dataset.id, topic)

    def _syndicate(self, dataset):
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
