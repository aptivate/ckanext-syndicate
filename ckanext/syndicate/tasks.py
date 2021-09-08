from __future__ import annotations

from typing import Any, Optional
from ckanext.syndicate.interfaces import ISyndicate
import logging
from urllib.parse import urljoin

import ckanapi
import requests

import ckantoolkit as toolkit
import ckan.plugins as plugins
from ckan import model

from . import signals
from .types import Profile, Topic
from .utils import deprecated

log = logging.getLogger(__name__)


def sync_package_task(package: str, action: Topic, profile: Profile):
    log.info("Sync package %s, with action %s" % (package, action))
    return sync_package(package, action, profile)


def get_target(target_url, target_api):
    ckan = ckanapi.RemoteCKAN(target_url, apikey=target_api)
    return ckan


def filter_extras(extras, profile: Profile):
    extras_dict = dict([(o["key"], o["value"]) for o in extras])
    extras_dict.pop(profile["syndicate_field_id"], None)
    return [{"key": k, "value": v} for (k, v) in extras_dict.items()]


def filter_resources(resources):
    return [{"url": r["url"], "name": r["name"]} for r in resources]


def sync_package(package_id: str, action: Topic, profile: Profile):
    log.info("sync package {0}".format(package_id))

    # load the package at run of time task (rather than use package state at
    # time of task creation).
    context = {
        "ignore_auth": True,
        "use_cache": False,
        "validate": False,
    }

    params = {
        "id": package_id,
    }
    package: dict[str, Any] = toolkit.get_action("package_show")(
        context,
        params,
    )

    try:
        toolkit.get_action("before_syndication_action")(
            {"profile": profile}, params
        )
    except KeyError:
        pass
    else:
        deprecated(
            "before_syndication_action is deprecated. Use before_syndication signal instead"
        )
    signals.before_syndication.send(package_id, profile=profile, params=params)

    if action == "dataset/create":
        _sync_create(package, profile)
    elif action == "dataset/update":
        _sync_update(package, profile)

    try:
        toolkit.get_action("after_syndication_action")(
            {"profile": profile}, params
        )
    except KeyError:
        pass
    else:
        deprecated(
            "after_syndication_action is deprecated. Use after_syndication signal instead"
        )
    signals.after_syndication.send(package_id, profile=profile, params=params)


def replicate_remote_organization(org, profile: Profile):
    ckan = get_target(profile["syndicate_url"], profile["syndicate_api_key"])
    remote_org = None

    try:
        remote_org = ckan.action.organization_show(id=org["name"])
    except toolkit.ObjectNotFound:
        log.error("Organization not found, creating new Organization.")
    except (toolkit.NotAuthorized, ckanapi.CKANAPIError) as e:
        log.error("Replication error(trying to continue): {}".format(e))
    except Exception as e:
        log.error("Replication error: {}".format(e))
        raise

    if not remote_org:
        org.pop("id")
        org.pop("image_url", None)
        org.pop("num_followers", None)
        org.pop("tags", None)
        org.pop("users", None)
        org.pop("groups", None)

        default_img_url = urljoin(
            ckan.address, "/base/images/placeholder-organization.png"
        )
        image_url = org.pop("image_display_url", default_img_url)
        image_fd = requests.get(image_url, stream=True, timeout=2).raw
        org.update(image_upload=image_fd)

        remote_org = ckan.action.organization_create(**org)

    return remote_org["id"]


def _sync_create(package, profile: Profile):
    ckan = get_target(profile["syndicate_url"], profile["syndicate_api_key"])

    # Create a new package based on the local instance
    new_package_data = dict(package)
    del new_package_data["id"]

    # Take syndicate prefix from profile or use global config prefix
    syndicate_name_prefix = profile["syndicate_prefix"]

    new_package_data["name"] = "%s-%s" % (
        syndicate_name_prefix,
        new_package_data["name"],
    )

    new_package_data["extras"] = filter_extras(
        new_package_data["extras"], profile
    )
    new_package_data["resources"] = filter_resources(package["resources"])

    org = new_package_data.pop("organization")

    if profile["syndicate_replicate_organization"]:
        org_id = replicate_remote_organization(org, profile)
    else:
        # Take syndicated org from the profile or use global config org
        org_id = profile["syndicate_organization"]
    new_package_data["owner_org"] = org_id

    try:
        # TODO: No automated test
        new_package_data = toolkit.get_action(
            "update_dataset_for_syndication"
        )({}, {"dataset_dict": new_package_data, "package_id": package["id"]})
    except KeyError as e:
        pass
    else:
        deprecated(
            "update_dataset_for_syndication is deprecated. Implement ISyndicate instead"
        )
    for plugin in plugins.PluginImplementations(ISyndicate):
        new_package_data = plugin.prepare_package_for_syndication(
            package["id"], new_package_data, profile
        )

    try:
        new_package_data["dataset_source"] = org_id
        remote_package = ckan.action.package_create(**new_package_data)
        set_syndicated_id(
            package,
            remote_package["id"],
            profile["syndicate_field_id"],
        )
    except toolkit.ValidationError as e:
        log.info("Remote create failed with: '{}'".format(str(e)))
        if "That URL is already in use." in e.error_dict.get("name", []):
            log.info(
                "package with name '{0}' already exists. Check creator.".format(
                    new_package_data["name"]
                )
            )

            # Take syndicated author from the profile or use global config author
            author = profile["syndicate_author"]
            if not author:
                raise
            try:
                remote_package = ckan.action.package_show(
                    id=new_package_data["name"]
                )
                remote_user = ckan.action.user_show(id=author)
            except toolkit.ValidationError as e:
                log.error(e.errors)
                raise
            except toolkit.ObjectNotFound:
                log.error('User "{0}" not found'.format(author))
                raise
            else:
                if remote_package["creator_user_id"] == remote_user["id"]:
                    log.info(
                        "Author is the same({0}). Updating".format(author)
                    )

                    ckan.action.package_update(
                        id=remote_package["id"], **new_package_data
                    )
                    set_syndicated_id(
                        package,
                        remote_package["id"],
                        profile["syndicate_field_id"],
                    )
                else:
                    log.info(
                        "Creator of remote package '{0}' did not match '{1}'. Skipping".format(
                            remote_user["name"], author
                        )
                    )


def _sync_update(package, profile: Profile):
    ckan = get_target(profile["syndicate_url"], profile["syndicate_api_key"])

    syndicated_id: Optional[str] = toolkit.h.get_pkg_dict_extra(
        package, profile["syndicate_field_id"]
    )

    if syndicated_id:
        try:
            ckan.action.package_show(id=syndicated_id)
        except ckanapi.NotFound:
            syndicated_id = None

    if not syndicated_id:
        return _sync_create(package, profile)

    # TODO: maybe we should do deepcopy
    updated_package = dict(package)
    # Keep the existing remote ID and Name
    del updated_package["id"]
    del updated_package["name"]

    updated_package["extras"] = filter_extras(package["extras"], profile)
    updated_package["resources"] = filter_resources(package["resources"])

    org = updated_package.pop("organization")

    if profile["syndicate_replicate_organization"]:
        org_id = replicate_remote_organization(org, profile)
    else:
        # Take syndicated org from the profile or use global config org
        org_id = profile["syndicate_organization"]

    updated_package["owner_org"] = org_id

    try:
        updated_package = toolkit.get_action("update_dataset_for_syndication")(
            {},
            {"dataset_dict": updated_package, "package_id": package["id"]},
        )
    except KeyError as e:
        pass
    else:
        deprecated(
            "update_dataset_for_syndication is deprecated. Implement ISyndicate instead"
        )
    for plugin in plugins.PluginImplementations(ISyndicate):
        updated_package = plugin.prepare_package_for_syndication(
            package["id"], updated_package, profile
        )

    try:
        ckan.action.package_update(id=syndicated_id, **updated_package)

    except ckanapi.ValidationError as e:
        # Extra check for new CKAN dataset deletion logic added at CKAN 2.7 and higher
        if "That URL is already in use." in e.error_dict.get("name", []):
            log.info("Syndicated_id exist.")
            # Take syndicated author from the profile or use global config author
            log.info(
                "package with name '{0}' already exists. Check creator.".format(
                    updated_package["name"]
                )
            )
            author = profile["syndicate_author"]
            if not author:
                raise
            try:
                remote_package = ckan.action.package_show(
                    id=updated_package["name"]
                )
                remote_user = ckan.action.user_show(id=author)
            except ckanapi.ValidationError as e:
                log.error(e.error_dict)
                raise
            except ckanapi.NotFound:
                log.error('User "{0}" not found'.format(author))
                raise
            else:
                if remote_package["creator_user_id"] == remote_user["id"]:
                    log.info(
                        "Author is the same({0}). Updating".format(author)
                    )

                    ckan.action.package_update(
                        id=remote_package["id"], **updated_package
                    )
                    set_syndicated_id(
                        package,
                        remote_package["id"],
                        profile["syndicate_field_id"],
                    )

                else:
                    log.info(
                        "Creator of remote package '{0}' did not match '{1}'. Skipping".format(
                            remote_user["name"], author
                        )
                    )
    except requests.ConnectionError as e:
        log.error("Package update error", exc_info=e)


def set_syndicated_id(local_package, remote_package_id, field_id):
    """Set the remote package id on the local package"""
    ext_id = (
        model.Session.query(model.PackageExtra.id)
        .join(model.Package, model.Package.id == model.PackageExtra.package_id)
        .filter(
            model.Package.id == local_package["id"],
            model.PackageExtra.key == field_id,
        )
        .first()
    )
    if not ext_id:
        if not toolkit.check_ckan_version("2.9"):
            rev = model.repo.new_revision()
        existing = model.PackageExtra(
            package_id=local_package["id"],
            key=field_id,
            value=remote_package_id,
        )
        model.Session.add(existing)
        model.Session.commit()
        model.Session.flush()
    else:
        model.Session.query(model.PackageExtra).filter_by(id=ext_id).update(
            {"value": remote_package_id, "state": "active"}
        )
    _update_search_index(local_package["id"], log)


def _update_search_index(package_id, log):
    """
    Tells CKAN to update its search index for a given package.
    """
    from ckan import model
    from ckan.lib.search.index import PackageSearchIndex

    package_index = PackageSearchIndex()
    context_ = {
        "model": model,
        "ignore_auth": True,
        "session": model.Session,
        "use_cache": False,
        "validate": False,
    }
    package = toolkit.get_action("package_show")(context_, {"id": package_id})
    package_index.index_package(package, defer_commit=False)
    log.info("Search indexed %s", package["name"])
