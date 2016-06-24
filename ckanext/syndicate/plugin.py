import os

import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
from ckan.lib.celery_app import celery
from ckan.lib.helpers import asbool

from pylons import config
import ckan.model as model
from ckan.model.domain_object import DomainObjectOperation

import uuid


SYNDICATE_FLAG = 'syndicate'


def syndicate_dataset(package_id, topic):
    ckan_ini_filepath = os.path.abspath(config['__file__'])
    celery.send_task(
        'syndicate.sync_package',
        args=[package_id, topic, ckan_ini_filepath],
        task_id='{}-{}'.format(str(uuid.uuid4()), package_id)
    )


def syndicate_resource(package_id, resource_id, topic):
    ckan_ini_filepath = os.path.abspath(config['__file__'])
    celery.send_task(
        'syndicate.sync_resource',
        args=[package_id, resource_id, topic, ckan_ini_filepath],
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

        if isinstance(entity, model.Resource):
            topic = self._get_topic('resource', operation)

            dataset = model.Package.get(entity.get_package_id())

            syndicate_resource(dataset.id, entity.id, topic)

            return

        if isinstance(entity, model.Package):
            topic = self._get_topic('dataset', operation)

            if asbool(entity.extras.get(SYNDICATE_FLAG, 'false')):
                syndicate_dataset(entity.id, topic)

    def _get_topic(self, prefix, operation):
        topics = {
            DomainObjectOperation.new: 'create',
            DomainObjectOperation.changed: 'update',
            DomainObjectOperation.deleted: 'delete',
        }

        topic = topics.get(operation, None)

        if topic is not None:
            return '{0}/{1}'.format(prefix, topic)

        return None
