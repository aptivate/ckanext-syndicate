from __future__ import annotations

import uuid

from typing import Any, Optional
from ckanext.syndicate.interfaces import ISyndicate
import logging
from urllib.parse import urljoin

import ckanapi
import requests

import ckantoolkit as toolkit
import ckan.plugins as plugins
from ckan import model
from ckan.lib.search import rebuild

from . import signals
from .types import Profile, Topic
from .utils import deprecated

log = logging.getLogger(__name__)


def sync_package_task(package: str, action: Topic, profile: Profile):
    return sync_package(package, action, profile)


def get_target(target_url, target_api):
    ckan = ckanapi.RemoteCKAN(target_url, apikey=target_api)
    return ckan


def filter_extras(extras, profile: Profile):
    extras_dict = dict([(o["key"], o["value"]) for o in extras])
    extras_dict.pop(profile["field_id"], None)
    return [{"key": k, "value": v} for (k, v) in extras_dict.items()]


def filter_resources(resources):
    return [{"url": r["url"], "name": r["name"]} for r in resources]


def sync_package(package_id: str, action: Topic, profile: Profile):
    log.info("Sync package %s, with action %s" % (package_id, action))

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

    _notify_before(package_id, profile, params)

    if action == "dataset/create":
        _sync_create(package, profile)
    elif action == "dataset/update":
        _sync_update(package, profile)

    _notify_after(package_id, profile, params)


def _notify_before(package_id, profile, params):
    try:
        toolkit.get_action("before_syndication_action")(
            {"profile": profile}, params
        )
    except KeyError:
        pass
    else:
        deprecated(
            "before_syndication_action is deprecated. Use before_syndication"
            " signal instead"
        )
    signals.before_syndication.send(package_id, profile=profile, params=params)


def _notify_after(package_id, profile, params):
    try:
        toolkit.get_action("after_syndication_action")(
            {"profile": profile}, params
        )
    except KeyError:
        pass
    else:
        deprecated(
            "after_syndication_action is deprecated. Use after_syndication"
            " signal instead"
        )
    signals.after_syndication.send(package_id, profile=profile, params=params)


def replicate_remote_organization(org: dict[str, Any], profile: Profile):
    ckan = get_target(profile["url"], profile["api_key"])
    remote_org = None

    try:
        remote_org = ckan.action.organization_show(id=org["name"])
    except ckanapi.NotFound:
        log.error(
            "Organization %s not found, creating new Organization.",
            org["name"],
        )
    except (ckanapi.NotAuthorized, ckanapi.CKANAPIError) as e:
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

        default_img_url = (
            "https://www.gravatar.com/avatar/123?s=400&d=identicon"
        )
        image_url = org.pop("image_display_url", default_img_url)
        image_fd = requests.get(image_url, stream=True, timeout=2).raw
        org.update(image_upload=image_fd)

        remote_org = ckan.action.organization_create(**org)

    return remote_org["id"]


def _sync_create(package: dict[str, Any], profile: Profile):
    ckan = get_target(profile["url"], profile["api_key"])

    # Create a new package based on the local instance
    new_package_data = dict(package)
    del new_package_data["id"]

    # Take syndicate prefix from profile or use global config prefix
    syndicate_name_prefix = profile["prefix"]

    name = "%s-%s" % (
        syndicate_name_prefix,
        new_package_data["name"],
    )
    if len(name) > 100:
        uniq = str(uuid.uuid3(uuid.NAMESPACE_DNS, name))
        name = name[92:] + uniq[:8]

    new_package_data["name"] = name
    new_package_data["extras"] = filter_extras(
        new_package_data["extras"], profile
    )
    new_package_data["resources"] = filter_resources(package["resources"])

    org = new_package_data.pop("organization")

    if profile["replicate_organization"]:
        org_id = replicate_remote_organization(org, profile)
    else:
        # Take syndicated org from the profile or use global config org
        org_id = profile["organization"]
    new_package_data["owner_org"] = org_id

    new_package_data = _prepare(package["id"], new_package_data, profile)
    try:
        new_package_data["dataset_source"] = org_id
        remote_package = ckan.action.package_create(**new_package_data)
        set_syndicated_id(
            package["id"],
            remote_package["id"],
            profile["field_id"],
        )
    except ckanapi.ValidationError as e:
        if "That URL is already in use." in e.error_dict.get("name", []):
            _reattach_own_package(
                package["id"], new_package_data, profile, ckan
            )
        else:
            raise


def _sync_update(package: dict[str, Any], profile: Profile):
    ckan = get_target(profile["url"], profile["api_key"])

    syndicated_id: Optional[str] = toolkit.h.get_pkg_dict_extra(
        package, profile["field_id"]
    )
    if not syndicated_id:
        return _sync_create(package, profile)
    try:
        remote_package = ckan.action.package_show(id=syndicated_id)
    except ckanapi.NotFound:
        return _sync_create(package, profile)

    # TODO: maybe we should do deepcopy
    updated_package = dict(package)
    # Keep the existing remote ID and Name
    updated_package["id"] = remote_package["id"]
    updated_package["name"] = remote_package["name"]

    updated_package["extras"] = filter_extras(package["extras"], profile)
    updated_package["resources"] = filter_resources(package["resources"])

    org = updated_package.pop("organization")

    if profile["replicate_organization"]:
        org_id = replicate_remote_organization(org, profile)
    else:
        # Take syndicated org from the profile or use global config org
        org_id = profile["organization"]

    updated_package["owner_org"] = org_id

    updated_package = _prepare(package["id"], updated_package, profile)

    try:
        ckan.action.package_update(**updated_package)
    except ckanapi.ValidationError as e:
        if "That URL is already in use." in e.error_dict.get("name", []):
            _reattach_own_package(
                package["id"], updated_package, profile, ckan
            )
        else:
            raise


def _prepare(
    local_id: str, package: dict[str, Any], profile: Profile
) -> dict[str, Any]:
    try:
        package = toolkit.get_action("update_dataset_for_syndication")(
            {},
            {"dataset_dict": package, "package_id": local_id},
        )
    except KeyError as e:
        pass
    else:
        deprecated(
            "update_dataset_for_syndication is deprecated. Implement"
            " ISyndicate instead"
        )
    for plugin in plugins.PluginImplementations(ISyndicate):
        package = plugin.prepare_package_for_syndication(
            local_id, package, profile
        )

    return package


def _reattach_own_package(
    local_id: str,
    package: dict[str, Any],
    profile: Profile,
    ckan: ckanapi.RemoteCKAN,
):

    log.warning(
        "There is a package with the same name on remote portal: %s.",
        package["name"],
    )
    author = profile["author"]
    if not author:
        raise
    try:
        remote_package = ckan.action.package_show(id=package["name"])
    except ckanapi.NotFound:
        log.error("Current user does not have access to read remote package")
        return False

    try:
        remote_user = ckan.action.user_show(id=author)
    except ckanapi.NotFound:
        log.error('User "{0}" not found on remote portal'.format(author))
        return False

    if remote_package["creator_user_id"] != remote_user["id"]:
        log.error(
            "Creator of remote package '{0}' did not match '{1}'. Skipping"
            .format(remote_user["name"], author)
        )

    log.info("Author is the same({0}). Updating".format(author))

    ckan.action.package_update(id=remote_package["id"], **package)
    set_syndicated_id(
        local_id,
        remote_package["id"],
        profile["syndicate_field_id"],
    )


def set_syndicated_id(local_id: str, remote_package_id: str, field_id: str):
    """Set the remote package id on the local package"""
    ext_id = (
        model.Session.query(model.PackageExtra.id)
        .join(model.Package, model.Package.id == model.PackageExtra.package_id)
        .filter(
            model.Package.id == local_id,
            model.PackageExtra.key == field_id,
        )
        .first()
    )
    if not ext_id:
        existing = model.PackageExtra(
            package_id=local_id,
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
        rebuild(local_id)
