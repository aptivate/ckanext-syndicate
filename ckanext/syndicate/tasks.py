from __future__ import annotations

import contextlib
import logging
import uuid
from typing import Any, Optional

import ckan.plugins as plugins
import ckan.plugins.toolkit as tk
import ckanapi
import requests
from ckan import model
from ckan.lib.search import rebuild

from ckanext.syndicate.interfaces import ISyndicate

from . import signals
from .types import Profile, Topic
from .utils import deprecated

log = logging.getLogger(__name__)


def get_target(url, apikey):
    ckan = ckanapi.RemoteCKAN(url, apikey=apikey)
    return ckan


def sync_package(package_id: str, action: Topic, profile: Profile):
    log.info("Sync package %s, with action %s" % (package_id, action))

    # load the package at run of time task (rather than use package state at
    # time of task creation).
    params = {
        "id": package_id,
    }
    package: dict[str, Any] = tk.get_action("package_show")(
        {
            "ignore_auth": True,
            "use_cache": False,
            "validate": False,
        },
        params,
    )

    _notify_before(package_id, profile, params)

    if action is Topic.create:
        _create(package, profile)
    elif action is Topic.update:
        _update(package, profile)

    _notify_after(package_id, profile, params)


def _notify_before(package_id, profile, params):
    try:
        tk.get_action("before_syndication_action")(
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
        tk.get_action("after_syndication_action")({"profile": profile}, params)
    except KeyError:
        pass
    else:
        deprecated(
            "after_syndication_action is deprecated. Use after_syndication"
            " signal instead"
        )
    signals.after_syndication.send(package_id, profile=profile, params=params)


def replicate_remote_organization(org: dict[str, Any], profile: Profile):
    ckan = get_target(profile.ckan_url, profile.api_key)
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


def _create(package: dict[str, Any], profile: Profile):
    ckan = get_target(profile.ckan_url, profile.api_key)

    # Create a new package based on the local instance
    new_package_data = dict(package)
    del new_package_data["id"]

    new_package_data["name"] = _compute_remote_name(package, profile)

    new_package_data = _prepare(package["id"], new_package_data, profile)

    with reattaching_context(package["id"], new_package_data, profile, ckan):
        remote_package = ckan.action.package_create(**new_package_data)
        set_syndicated_id(
            package["id"],
            remote_package["id"],
            profile.field_id,
        )


def _update(package: dict[str, Any], profile: Profile):
    ckan = get_target(profile.ckan_url, profile.api_key)

    syndicated_id: Optional[str] = tk.h.get_pkg_dict_extra(
        package, profile.field_id
    )
    if not syndicated_id:
        return _create(package, profile)
    try:
        remote_package = ckan.action.package_show(id=syndicated_id)
    except ckanapi.NotFound:
        return _create(package, profile)

    # TODO: maybe we should do deepcopy
    updated_package = dict(package)
    # Keep the existing remote ID and Name
    updated_package["id"] = remote_package["id"]
    updated_package["name"] = remote_package["name"]

    updated_package = _prepare(package["id"], updated_package, profile)

    with reattaching_context(package["id"], updated_package, profile, ckan):
        ckan.action.package_update(**updated_package)


def _compute_remote_name(package: dict[str, Any], profile: Profile):
    name = "%s-%s" % (
        profile.name_prefix,
        package["name"],
    )
    if len(name) > 100:
        uniq = str(uuid.uuid3(uuid.NAMESPACE_DNS, name))
        name = name[92:] + uniq[:8]
    return name


def _normalize_org_id(package: dict[str, Any], profile: Profile):
    org = package.pop("organization")
    if profile.replicate_organization:
        org_id = replicate_remote_organization(org, profile)
    else:
        # Take syndicated org from the profile or use global config org
        org_id = profile.organization
    return org_id


def _prepare(
    local_id: str, package: dict[str, Any], profile: Profile
) -> dict[str, Any]:
    extras_dict = dict([(o["key"], o["value"]) for o in package["extras"]])
    extras_dict.pop(profile.field_id, None)
    package["extras"] = [
        {"key": k, "value": v} for (k, v) in extras_dict.items()
    ]

    package["resources"] = [
        {"url": r["url"], "name": r["name"]} for r in package["resources"]
    ]
    package["owner_org"] = _normalize_org_id(package, profile)

    try:
        package = tk.get_action("update_dataset_for_syndication")(
            {},
            {"dataset_dict": package, "package_id": local_id},
        )
    except KeyError:
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


def set_syndicated_id(local_id: str, remote_id: str, field: str):
    """Set the remote package id on the local package"""
    ext_id = (
        model.Session.query(model.PackageExtra.id)
        .join(model.Package, model.Package.id == model.PackageExtra.package_id)
        .filter(
            model.Package.id == local_id,
            model.PackageExtra.key == field,
        )
        .first()
    )
    if not ext_id:
        existing = model.PackageExtra(
            package_id=local_id,
            key=field,
            value=remote_id,
        )
        model.Session.add(existing)
        model.Session.commit()
        model.Session.flush()
    else:
        model.Session.query(model.PackageExtra).filter_by(id=ext_id).update(
            {"value": remote_id, "state": "active"}
        )
    rebuild(local_id)


@contextlib.contextmanager
def reattaching_context(
    local_id: str,
    package: dict[str, Any],
    profile: Profile,
    ckan: ckanapi.RemoteCKAN,
):
    try:
        yield
    except ckanapi.ValidationError as e:
        if "That URL is already in use." not in e.error_dict.get("name", []):
            raise
    else:
        return

    log.warning(
        "There is a package with the same name on remote portal: %s.",
        package["name"],
    )
    author = profile.author
    if not author:
        log.error(
            "Profile %s does not have author set. Skip syndication", profile.id
        )
        return

    try:
        remote_package = ckan.action.package_show(id=package["name"])
    except ckanapi.NotFound:
        log.error(
            "Current user does not have access to read remote package. Skip"
            " syndication"
        )
        return

    try:
        remote_user = ckan.action.user_show(id=author)
    except ckanapi.NotFound:
        log.error(
            'User "{0}" not found on remote portal. Skip syndication'.format(
                author
            )
        )
        return

    if remote_package["creator_user_id"] != remote_user["id"]:
        log.error(
            "Creator of remote package %s did not match '%s(%s)'. Skip"
            " syndication",
            remote_package["creator_user_id"],
            author,
            remote_user["id"],
        )
        return

    log.info("Author is the same({0}). Continue syndication".format(author))

    ckan.action.package_update(id=remote_package["id"], **package)
    set_syndicated_id(
        local_id,
        remote_package["id"],
        profile.field_id,
    )
