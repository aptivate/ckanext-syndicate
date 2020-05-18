# -*- coding: utf-8 -*-
from __future__ import print_function
import os
import logging

from time import sleep

import ckan.model as ckan_model
import ckan.plugins.toolkit as tk
from ckan.plugins import get_plugin

import ckanext.syndicate.syndicate_model.model as model
from ckanext.syndicate.syndicate_model.syndicate_config import SyndicateConfig
try:
    from itertools import zip_longest
except ImportError:
    from itertools import izip_longest as zip_longest

if tk.check_ckan_version("2.9"):
    config = tk.config
else:
    from pylons import config


log = logging.getLogger(__name__)


def syndicate_dataset(package_id, topic, profile=None):
    import ckanext.syndicate.tasks as tasks

    ckan_ini_filepath = os.path.abspath(config["__file__"])
    _compat_enqueue(
        "syndicate.sync_package",
        tasks.sync_package_task,
        [package_id, topic, ckan_ini_filepath, profile],
    )


def _compat_enqueue(name, fn, args=None):
    u"""
    Enqueue a background job using Celery or RQ.
    """
    try:
        # Try to use RQ
        from ckan.plugins.toolkit import enqueue_job

        enqueue_job(fn, args=args)
    except ImportError:
        # Fallback to Celery
        import uuid
        from ckan.lib.celery_app import celery

        celery.send_task(name, args=args, task_id=str(uuid.uuid4()))


def prepare_profile_dict(profile):
    profile_dict = {
        "id": profile.id,
        "syndicate_url": profile.syndicate_url,
        "syndicate_api_key": profile.syndicate_api_key,
        "syndicate_organization": profile.syndicate_organization,
        "syndicate_flag": profile.syndicate_flag,
        "syndicate_field_id": profile.syndicate_field_id,
        "syndicate_prefix": profile.syndicate_prefix,
        "syndicate_replicate_organization": profile.syndicate_replicate_organization,
        "syndicate_author": profile.syndicate_author,
        "predicate": profile.predicate,
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


def seed_db():
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
        "prefix",
    )
    profile_lists = zip_longest(
        *[tk.aslist(config.get(prefix + key)) for key in keys]
    )
    for item in profile_lists:
        profile = SyndicateConfig._for_seed(item)
        ckan_model.Session.add(profile)
        print("Added profile: {}".format(profile))
    ckan_model.Session.commit()


def sync_portals(pkg=None):
    plugin = get_plugin("syndicate")
    from ckanext.syndicate.plugin import get_syndicate_flag

    if pkg:
        pkg_obj = ckan_model.Package.get(pkg)
        packages = [pkg_obj] if pkg_obj else []
    else:
        packages = ckan_model.Session.query(ckan_model.Package).filter_by(
            state="active"
        )

    for package in packages:
        sleep(0.1)
        package.extras[get_syndicate_flag()] = "true"
        print("Sending syndication signal to {}".format(package.id))
        plugin.notify(package, "changed")
