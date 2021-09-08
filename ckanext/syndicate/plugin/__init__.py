import json
import logging
import importlib

import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit

import ckan.model as model
from ckan.model.domain_object import DomainObjectOperation
from ckanext.syndicate.syndicate_model.syndicate_config import SyndicateConfig
import ckanext.syndicate.actions as actions
import ckanext.syndicate.utils as utils
import ckanext.syndicate.cli as cli

config = toolkit.config


syndicate_dataset = utils.syndicate_dataset

log = logging.getLogger(__name__)


def _convert_from_json(value):
    if value is not toolkit.missing:
        try:
            value = json.loads(value)
        except ValueError:
            log.error(
                "Error during unserializing json in validator", exc_info=True
            )
    return value


def _convert_to_json(value):
    return json.dumps(value)


def _get_syndicate_endpoints():
    return [profile["syndicate_url"] for profile in _get_syndicate_profiles()]


def get_syndicate_flag():
    return config.get("ckan.syndicate.flag", "syndicate")


def get_syndicated_id():
    return config.get("ckan.syndicate.id", "syndicated_id")


def get_syndicated_author():
    return config.get("ckan.syndicate.author")


def get_syndicated_name_prefix():
    return config.get("ckan.syndicate.name_prefix", "")


def get_syndicated_organization():
    return config.get("ckan.syndicate.organization", None)


def is_organization_preserved():
    return toolkit.asbool(
        config.get("ckan.syndicate.replicate_organization", False)
    )


def _get_syndicate_profiles():
    profiles_list = []
    profiles = model.Session.query(SyndicateConfig).all()

    for profile in profiles:
        profiles_list.append(utils.prepare_profile_dict(profile))

    return profiles_list


class SyndicatePlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IDomainObjectModification, inherit=True)
    plugins.implements(plugins.IValidators)
    plugins.implements(plugins.ITemplateHelpers)
    plugins.implements(plugins.IActions)
    plugins.implements(plugins.IClick)

    # IClick

    def get_commands(self):
        return cli.get_commands()

    # IActions

    def get_actions(self):
        return actions.get_actions()

    # ITemplateHelpers

    def get_helpers(self):
        return dict(get_syndicate_endpoints=_get_syndicate_endpoints)

    # IValidators

    def get_validators(self):
        return dict(
            convert_from_json=_convert_from_json,
            convert_to_json=_convert_to_json,
        )

    # Based on ckanext-webhooks plugin
    # IDomainObjectNotification & IResourceURLChange
    def notify(self, entity, operation=None):
        if not operation:
            # This happens on IResourceURLChange
            return

        if isinstance(entity, model.Package):
            self._syndicate_dataset(entity, operation)

    def _syndicate_dataset(self, dataset, operation):
        topic = self._get_topic("dataset", operation)
        if topic is None:
            log.debug(
                "Notification topic for operation [%s] is not defined",
                operation,
            )
            return

        # Get syndication profiles from db
        syndicate_profiles = _get_syndicate_profiles()
        if syndicate_profiles:
            for profile in syndicate_profiles:
                str_endpoints = dataset.extras.get(
                    u"syndication_endpoints", u"[]"
                )
                try:
                    endpoints = json.loads(str_endpoints)
                except ValueError:
                    log.error(
                        (
                            "Failed to unserialize "
                            "syndication endpoints of <{}>"
                        ).format(dataset.id),
                        exc_info=True,
                    )
                    endpoints = []
                if endpoints and profile["syndicate_url"] not in endpoints:
                    log.debug(
                        "Skip endpoint {} for <{}>".format(
                            profile["syndicate_url"], dataset.id
                        )
                    )
                    continue
                if profile["predicate"]:
                    lib, func = profile["predicate"].split(":")
                    module = importlib.import_module(lib)
                    predicate = getattr(module, func)
                    if not predicate(dataset):
                        log.info(
                            "Dataset[{}] will not syndicate becaus of predicate[{}] rejection".format(
                                dataset.id, profile["predicate"]
                            )
                        )
                        continue
                if self._syndicate(dataset, profile["syndicate_flag"]):
                    log.debug(
                        "Syndicate <{}> to {}".format(
                            dataset.id, profile["syndicate_url"]
                        )
                    )
                    syndicate_dataset(dataset.id, topic, profile)
                else:
                    continue
        else:
            if self._syndicate(dataset):
                syndicate_dataset(dataset.id, topic)

    def _syndicate(self, dataset, syndicate_flag=None):
        if syndicate_flag:
            return not dataset.private and toolkit.asbool(
                dataset.extras.get(syndicate_flag, "false")
            )
        else:
            return not dataset.private and toolkit.asbool(
                dataset.extras.get(get_syndicate_flag(), "false")
            )

    def _get_topic(self, prefix, operation):
        topics = {
            DomainObjectOperation.new: "create",
            DomainObjectOperation.changed: "update",
        }
        topic = topics.get(operation)
        if topic:
            return "{0}/{1}".format(prefix, topic)
