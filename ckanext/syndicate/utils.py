# -*- coding: utf-8 -*-
from __future__ import annotations
import json
import warnings
import logging
from collections import defaultdict

from itertools import zip_longest
from typing import Iterable, Iterator, Type

import ckan.model as ckan_model
import ckan.plugins.toolkit as tk
from ckan.plugins import get_plugin

from ckanext.syndicate.types import Topic, Profile


CkanDeprecationWarning: Type

try:
    from ckan.exceptions import CkanDeprecationWarning  # type: ignore
except ImportError:
    CkanDeprecationWarning = DeprecationWarning


class SyndicationDeprecationWarning(CkanDeprecationWarning):
    pass


PROFILE_PREFIX = "ckanext.syndicate.profile."
log = logging.getLogger(__name__)


def deprecated(msg):
    log.warning(msg)
    warnings.warn(msg, category=SyndicationDeprecationWarning, stacklevel=3)


def syndicate_dataset(package_id: str, topic: Topic, profile: Profile):
    import ckanext.syndicate.tasks as tasks

    tk.enqueue_job(
        tasks.sync_package_task,
        [package_id, topic, profile],
    )


def prepare_profile_dict(profile: Profile) -> Profile:
    return profile


def syndicate_configs_from_config(config) -> Iterable[Profile]:
    prefix = "ckan.syndicate."
    keys = (
        "api_key",
        "author",
        "extras",
        "field_id",
        "flag",
        "organization",
        "predicate",
        "name_prefix",
        "replicate_organization",
        "ckan_url",
    )

    profile_lists = zip_longest(
        *[tk.aslist(config.get(prefix + key)) for key in keys]
    )
    for idx, item in enumerate(profile_lists):
        deprecated(
            f"Deprecated profile definition: {item}. Use"
            f" {PROFILE_PREFIX}*.OPTION form"
        )
        data = dict((k, v) for k, v in zip(keys, item) if v is not None)

        try:
            data["extras"] = json.loads(data.get("extras", "{}"))
        except (TypeError, ValueError):
            data["extras"] = {}
        yield Profile(id=str(idx), **data)

    yield from _parse_profiles(config)


def _parse_profiles(config: dict[str, str]) -> Iterable[Profile]:
    profiles = defaultdict(dict)
    for opt, v in config.items():
        if not opt.startswith(PROFILE_PREFIX):
            continue
        profile, attr = opt[len(PROFILE_PREFIX) :].split(".", 1)
        profiles[profile][attr] = v

    for id_, data in profiles.items():
        try:
            data["extras"] = json.loads(data.get("extras", "{}"))
        except (TypeError, ValueError):
            data["extras"] = {}

        yield Profile(id=id_, **data)


def get_syndicate_profiles() -> Iterator[Profile]:
    for profile in syndicate_configs_from_config(tk.config):
        yield prepare_profile_dict(profile)


def try_sync(id_):
    plugin = get_plugin("syndicate")

    pkg = ckan_model.Package.get(id_)
    if not pkg:
        return
    for profile in get_syndicate_profiles():
        pkg.extras[profile.field_id] = "true"
    plugin.notify(pkg, "changed")
