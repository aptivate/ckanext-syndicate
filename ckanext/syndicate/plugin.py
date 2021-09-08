from __future__ import annotations

import logging
import warnings

from typing import Iterable, Optional

from werkzeug.utils import import_string

import ckan.plugins as plugins
import ckan.plugins.toolkit as tk

import ckan.model as model
from ckan.model.domain_object import DomainObjectOperation

import ckanext.syndicate.actions as actions
import ckanext.syndicate.utils as utils
import ckanext.syndicate.cli as cli

from .interfaces import ISyndicate
from .types import Profile, Topic


log = logging.getLogger(__name__)


def get_syndicate_flag():
    return tk.config.get("ckan.syndicate.flag", "syndicate")


class SyndicatePlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IDomainObjectModification, inherit=True)
    plugins.implements(plugins.IActions)
    plugins.implements(plugins.IClick)
    plugins.implements(ISyndicate)
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

    # IActions

    def get_actions(self):
        return actions.get_actions()

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

    def skip_syndication(self, package, syndicate_flag):
        if package.private:
            return True

        syndicate = tk.asbool(package.extras.get(syndicate_flag, "false"))
        return not syndicate


def _get_topic(operation: str) -> Optional[Topic]:
    if operation == DomainObjectOperation.new:
        return "dataset/create"

    if operation == DomainObjectOperation.changed:
        return "dataset/update"


def _syndicate_dataset(dataset, operation):
    topic = _get_topic(operation)
    if topic is None:
        log.debug(
            "Notification topic for operation [%s] is not defined",
            operation,
        )
        return

    for profile in utils.get_syndicate_profiles():
        if profile["predicate"]:

            predicate = import_string(profile["predicate"], silent=True)
            if not predicate(dataset):
                log.info(
                    "Dataset[{}] will not syndicate becaus of predicate[{}] rejection".format(
                        dataset.id, profile["predicate"]
                    )
                )
                continue

        implementations = plugins.PluginImplementations(ISyndicate)
        if any(
            p.skip_syndication(dataset, profile["syndicate_flag"])
            for p in implementations
        ):
            continue

        log.debug(
            "Syndicate <{}> to {}".format(dataset.id, profile["syndicate_url"])
        )
        utils.syndicate_dataset(dataset.id, topic, profile)
