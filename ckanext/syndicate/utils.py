# -*- coding: utf-8 -*-
from __future__ import annotations


import warnings
import logging

from itertools import zip_longest
from typing import Iterable, Iterator, Type

import ckan.model as ckan_model
import ckan.plugins.toolkit as tk

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
        "syndicate_url": profile.syndicate_url or "",
        "syndicate_api_key": profile.syndicate_api_key or "",
        "syndicate_organization": profile.syndicate_organization or "",
        "syndicate_flag": profile.syndicate_flag or "syndicate",
        "syndicate_field_id": profile.syndicate_field_id or "syndicated_id",
        "syndicate_prefix": profile.syndicate_prefix or "",
        "syndicate_replicate_organization": profile.syndicate_replicate_organization
        or False,
        "syndicate_author": profile.syndicate_author or "",
        "predicate": profile.predicate or "",
    }

    return profile_dict


def reset_db():
    drop_db()
    create_db()
    seed_db()


def drop_db():
    model.drop_tables()


def create_db():
    model.create_tables()


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
        obj = SyndicateConfig._for_seed(item)
        obj.id = str(idx)
        yield obj


def seed_db():
    for profile in syndicate_configs_from_config(tk.config):
        ckan_model.Session.add(profile)
        print("Added profile: {}".format(profile))
    ckan_model.Session.commit()


def get_syndicate_profiles() -> Iterator[Profile]:
    for profile in syndicate_configs_from_config(tk.config):
        yield prepare_profile_dict(profile)
