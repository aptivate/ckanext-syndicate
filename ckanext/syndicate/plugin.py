import os

import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
from ckan.lib.celery_app import celery

from pylons import config
import ckan.model as model
from ckan.model.domain_object import DomainObjectOperation

import uuid


SYNDICATE_FLAG = 'syndicate'


def syndicate_task(package_id, topic):
    from pylons import config
    ckan_ini_filepath = os.path.abspath(config.__file__)
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
    #IDomainObjectNotification & #IResourceURLChange
    def notify(self, entity, operation=None):
        context = {'model': model, 'ignore_auth': True, 'defer_commit': True}

        if isinstance(entity, model.Resource):
            if not operation:
                #This happens on IResourceURLChange, but I'm not sure whether
                #to make this into a webhook.
                return
            elif operation == DomainObjectOperation.new:
                topic = 'resource/create'

            if operation == DomainObjectOperation.changed:
                topic = 'resource/update'

            elif operation == DomainObjectOperation.deleted:
                topic = 'resource/delete'

            else:
                return

        if isinstance(entity, model.Package):
            if operation == DomainObjectOperation.new:
                topic = 'dataset/create'

            elif operation == DomainObjectOperation.changed:
                topic = 'dataset/update'

            elif operation == DomainObjectOperation.deleted:
                topic = 'dataset/delete'

            else:
                return

        if entity.extras.get(SYNDICATE_FLAG, 'false') == 'true':
            syndicate_task(entity.id, topic)
