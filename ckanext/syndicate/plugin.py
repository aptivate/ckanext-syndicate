from __future__ import annotations

import logging
import warnings

from typing import Optional

from werkzeug.utils import import_string

import ckan.plugins as plugins
import ckan.plugins.toolkit as tk

import ckan.model as model
from ckan.model.domain_object import DomainObjectOperation

import ckanext.syndicate.utils as utils
import ckanext.syndicate.cli as cli

from .interfaces import ISyndicate
from .types import Topic


log = logging.getLogger(__name__)


def get_syndicate_flag():
    return tk.config.get("ckan.syndicate.flag", "syndicate")


class SyndicatePlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IDomainObjectModification, inherit=True)
    plugins.implements(plugins.IClick)
    plugins.implements(ISyndicate, inherit=True)
    plugins.implements(plugins.IConfigurable)

    # IConfigurable

    def configure(self, config):
        if tk.asbool(config.get("debug")):
            warnings.filterwarnings(
                "default", category=utils.SyndicationDeprecationWarning
            )

    # IClick

    def get_commands(self):
        return cli.get_commands()

    # Based on ckanext-webhooks plugin
    # IDomainObjectNotification & IResourceURLChange
    def notify(self, entity, operation=None):
        if not operation:
            # This happens on IResourceURLChange
            return

        if not isinstance(entity, model.Package):
            return

        _syndicate_dataset(entity, operation)

    # ISyndicate

    def skip_syndication(self, package: model.Package, profile: utils.Profile):
        if package.private:
            return True

        if profile.predicate:
            predicate = import_string(profile.predicate)
            if not predicate(package):
                log.info(
                    "Dataset[{}] will not syndicate because of predicate[{}]"
                    " rejection".format(package.id, profile.predicate)
                )
                return True

        syndicate = tk.asbool(package.extras.get(profile.flag, "false"))
        return not syndicate


def _get_topic(operation: str) -> Optional[Topic]:
    if operation == DomainObjectOperation.new:
        return "dataset/create"

    if operation == DomainObjectOperation.changed:
        return "dataset/update"


def _syndicate_dataset(package, operation):
    topic = _get_topic(operation)
    if topic is None:
        log.debug(
            "Notification topic for operation [%s] is not defined",
            operation,
        )
        return

    implementations = plugins.PluginImplementations(ISyndicate)
    skipper: ISyndicate = next(iter(implementations))

    for profile in utils.get_syndicate_profiles():
        if skipper.skip_syndication(package, profile):
            log.debug(
                "Plugin %s decided to skip syndication of %s for profile %s",
                skipper.name,
                package.id,
                profile.id,
            )
            continue

        log.debug("Syndicate <{}> to {}".format(package.id, profile.ckan_url))
        utils.syndicate_dataset(package.id, topic, profile)
