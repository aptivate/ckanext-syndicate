# -*- coding: utf-8 -*-
from __future__ import annotations
from collections import defaultdict


import warnings
import logging

from itertools import zip_longest
from typing import Iterable, Iterator, Type

import ckan.model as ckan_model
import ckan.plugins.toolkit as tk
from ckan.plugins import get_plugin

import ckanext.syndicate.syndicate_model.model as model
from ckanext.syndicate.syndicate_model.syndicate_config import SyndicateConfig
from ckanext.syndicate.types import Profile, Topic


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


def prepare_profile_dict(profile: SyndicateConfig) -> Profile:
    profile_dict: Profile = {
        "id": profile.id,
        "url": profile.syndicate_ckan_url or "",
        "api_key": profile.syndicate_api_key or "",
        "organization": profile.syndicate_organization or "",
        "flag": profile.syndicate_flag or "syndicate",
        "field_id": profile.syndicate_field_id or "syndicated_id",
        "prefix": profile.syndicate_prefix or "",
        "replicate_organization": profile.syndicate_replicate_organization
        or False,
        "author": profile.syndicate_author or "",
        "predicate": profile.predicate or "",
        "extras": profile.extras or {},
    }

    return profile_dict


def syndicate_configs_from_config(config) -> Iterable[SyndicateConfig]:
    prefix = "ckan.syndicate."
    keys = (
        "ckan_url",
        "api_key",
        "organization",
        "replicate_organization",
        "author",
        "predicate",
        "field_id",
        "flag",
        "name_prefix",
    )

    profile_lists = zip_longest(
        *[tk.aslist(config.get(prefix + key)) for key in keys]
    )
    for idx, item in enumerate(profile_lists):
        deprecated(
            f"Deprecated profile definition: {item}. Use"
            f" {PROFILE_PREFIX}*.OPTION form"
        )
        obj = SyndicateConfig._for_seed(item)
        obj.id = str(idx)
        yield obj

    yield from _parse_profiles(config)


def _parse_profiles(config: dict[str, str]) -> Iterable[SyndicateConfig]:
    profiles = defaultdict(dict)
    for opt, v in config.items():
        if not opt.startswith(PROFILE_PREFIX):
            continue
        profile, attr = opt[len(PROFILE_PREFIX) :].split(".", 1)
        key = "syndicate_" + attr if attr != "predicate" else attr
        profiles[profile][key] = v

    for id_, data in profiles.items():
        yield SyndicateConfig(id=id_, **data)


def get_syndicate_profiles() -> Iterator[Profile]:
    for profile in syndicate_configs_from_config(tk.config):
        yield prepare_profile_dict(profile)


def try_sync(id_):
    plugin = get_plugin("syndicate")

    pkg = ckan_model.Package.get(id_)
    if not pkg:
        return
    for profile in get_syndicate_profiles():
        pkg.extras[profile["field_id"]] = "true"
    plugin.notify(pkg, "changed")
