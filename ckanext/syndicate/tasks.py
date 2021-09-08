import logging
from six.moves.urllib.parse import urlparse, urljoin

import ckanapi
import routes
import ast
import requests
import six

import ckantoolkit as toolkit

from ckan.lib.helpers import get_pkg_dict_extra
from ckanext.syndicate.plugin import (
    get_syndicate_flag,
    get_syndicated_id,
    get_syndicated_name_prefix,
    get_syndicated_organization,
    get_syndicated_author,
    is_organization_preserved,
)
from ckan import model
from ckan.model.task_status import TaskStatus
from datetime import datetime
import json
from sqlalchemy.orm.exc import NoResultFound

try:
    from ckan.lib.celery_app import celery

    @celery.task(name="syndicate.sync_package")
    def sync_package_task_celery(*args, **kwargs):
        return sync_package_task(*args, **kwargs)


except ImportError:
    pass

config = toolkit.config


def sync_package_task(package, action, ckan_ini_filepath, profile=None):
    log = sync_package_task.get_logger()
    load_config(ckan_ini_filepath)
    log.info("Sync package %s, with action %s" % (package, action))
    return sync_package(package, action, None, profile)


# TODO: why mp this
# enable celery logging for when you run nosetests -s
log = logging.getLogger("ckanext.syndicate.tasks")


def get_logger():
    return log


sync_package_task.get_logger = get_logger


def load_config(ckan_ini_filepath):
    import ckan

    ckan.config.environment.load_environment(config)


def get_target(target_url="", target_api=""):
    if target_url and target_api:
        ckan_url = target_url
        api_key = target_api
        user_agent = config.get("ckan.syndicate.user_agent", None)
    else:
        if hasattr(get_target, "ckan"):
            return get_target.ckan
        ckan_url = config.get("ckan.syndicate.ckan_url")
        api_key = config.get("ckan.syndicate.api_key")
        user_agent = config.get("ckan.syndicate.user_agent", None)
        assert ckan_url and api_key, "Task must have ckan_url and api_key"

    ckan = ckanapi.RemoteCKAN(ckan_url, apikey=api_key, user_agent=user_agent)
    get_target.ckan = ckan

    return ckan


def filter_extras(extras):
    extras_dict = dict([(o["key"], o["value"]) for o in extras])
    extras_dict.pop(get_syndicate_flag(), None)
    return [{"key": k, "value": v} for (k, v) in extras_dict.items()]


def filter_resources(resources):
    return [{"url": r["url"], "name": r["name"]} for r in resources]


def sync_package(package_id, action, ckan_ini_filepath=None, profile=None):
    log.info("sync package {0}".format(package_id))

    # load the package at run of time task (rather than use package state at
    # time of task creation).
    context = {
        "model": model,
        "ignore_auth": True,
        "session": model.Session,
        "use_cache": False,
        "validate": False,
    }

    params = {
        "id": package_id,
    }
    package = toolkit.get_action("package_show")(
        context,
        params,
    )

    try:
        toolkit.get_action("before_syndication_action")(
            {"profile": profile}, params
        )
    except KeyError:
        pass
    if action == "dataset/create":
        _create_package(package, profile)
    elif action == "dataset/update":
        _update_package(package, profile)
    else:
        raise Exception("Unsupported action {0}".format(action))
    try:
        toolkit.get_action("after_syndication_action")(
            {"profile": profile}, params
        )
    except KeyError:
        pass


def replicate_remote_organization(org):
    ckan = get_target()
    remote_org = None

    try:
        remote_org = ckan.action.organization_show(id=org["name"])
    except toolkit.ObjectNotFound:
        log.error("Organization not found, creating new Organization.")
    except (toolkit.NotAuthorized, ckanapi.CKANAPIError) as e:
        log.error("Error replication error(trying to continue): {}".format(e))
    except Exception as e:
        log.error("Error replication error: {}".format(e))
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


def _create_package(package, profile=None):
    ckan = get_target(
        profile["syndicate_url"]
        if profile and profile.get("syndicate_url", "")
        else "",
        profile["syndicate_api_key"]
        if profile and profile.get("syndicate_api_key", "")
        else "",
    )
    syndicate_to_url = (
        profile["syndicate_url"]
        if profile and profile.get("syndicate_url", "")
        else config.get("ckan.syndicate.ckan_url")
    )
    # Create a new package based on the local instance
    new_package_data = dict(package)
    logging_id = new_package_data["id"]
    del new_package_data["id"]

    # Take syndicate prefix from profile or use global config prefix
    syndicate_name_prefix = (
        profile["syndicate_prefix"]
        if profile and profile.get("syndicate_prefix", "")
        else get_syndicated_name_prefix()
    )
    new_package_data["name"] = "%s-%s" % (
        syndicate_name_prefix,
        new_package_data["name"],
    )

    new_package_data["extras"] = filter_extras(new_package_data["extras"])
    new_package_data["resources"] = filter_resources(package["resources"])

    org = new_package_data.pop("organization")

    if profile:
        preserve_organization = profile.get(
            "syndicate_replicate_organization", False
        )
    else:
        preserve_organization = is_organization_preserved()
    if preserve_organization:
        org_id = replicate_remote_organization(org)
    else:
        # Take syndicated org from the profile or use global config org
        org_id = (
            profile["syndicate_organization"]
            if profile and profile.get("syndicate_organization", "")
            else get_syndicated_organization()
        )

    new_package_data["owner_org"] = org_id

    try:
        # TODO: No automated test
        new_package_data = toolkit.get_action(
            "update_dataset_for_syndication"
        )({}, {"dataset_dict": new_package_data, "package_id": package["id"]})
    except KeyError as e:
        log.error("Error in update_dataset_for_syndication: {0}".format(e))

    try:
        new_package_data["dataset_source"] = org_id
        remote_package = ckan.action.package_create(**new_package_data)
        set_syndicated_id(
            package,
            remote_package["id"],
            profile["syndicate_field_id"] if profile else "",
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
            author = (
                profile["syndicate_author"]
                if profile and profile.get("syndicate_author", "")
                else get_syndicated_author()
            )
            if author is None:
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
                        profile["syndicate_field_id"] if profile else "",
                    )
                else:
                    log.info(
                        "Creator of remote package '{0}' did not match '{1}'. Skipping".format(
                            remote_user["name"], author
                        )
                    )


def _update_package(package, profile=None):
    if profile and profile.get("syndicate_field_id", ""):
        syndicated_id = get_pkg_dict_extra(
            package, profile["syndicate_field_id"]
        )
        if syndicated_id is None and profile["syndicate_field_id"]:
            sync_id = (
                model.Session.query(model.PackageExtra)
                .filter(model.PackageExtra.package_id == package.get("id"))
                .filter(
                    model.PackageExtra.key == profile["syndicate_field_id"]
                )
                .first()
            )
            if sync_id and sync_id.state == "deleted":
                syndicated_id = sync_id.value
                model.Session.query(model.PackageExtra).filter_by(
                    id=sync_id.id
                ).update({"state": "active"})
    else:
        syndicated_id = get_pkg_dict_extra(package, get_syndicated_id())

    if syndicated_id is None:
        _create_package(package, profile)
        return

    ckan = get_target(
        profile["syndicate_url"]
        if profile and profile.get("syndicate_url", "")
        else "",
        profile["syndicate_api_key"]
        if profile and profile.get("syndicate_api_key", "")
        else "",
    )
    syndicate_to_url = (
        profile["syndicate_url"]
        if profile
        else config.get("ckan.syndicate.ckan_url")
    )

    try:
        updated_package = dict(package)
        logging_id = updated_package["id"]
        # Keep the existing remote ID and Name
        del updated_package["id"]
        del updated_package["name"]

        updated_package["extras"] = filter_extras(package["extras"])
        updated_package["resources"] = filter_resources(package["resources"])

        org = updated_package.pop("organization")

        if profile:
            preserve_organization = profile.get(
                "syndicate_replicate_organization", False
            )
        else:
            preserve_organization = is_organization_preserved()
        if preserve_organization:
            org_id = replicate_remote_organization(org)
        else:
            # Take syndicated org from the profile or use global config org
            org_id = (
                profile["syndicate_organization"]
                if profile and profile.get("syndicate_organization", "")
                else get_syndicated_organization()
            )

        updated_package["owner_org"] = org_id

        try:
            # TODO: No automated test
            updated_package = toolkit.get_action(
                "update_dataset_for_syndication"
            )(
                {},
                {"dataset_dict": updated_package, "package_id": package["id"]},
            )
        except KeyError as e:
            log.error("Error in update_dataset_for_syndication: {0}".format(e))
            pass

        try:
            ckan.action.package_update(id=syndicated_id, **updated_package)

        except toolkit.ValidationError as e:
            # Extra check for new CKAN dataset deletion logic added at CKAN 2.7 and higher
            if "That URL is already in use." in e.error_dict.get("name", []):
                log.info("Check syndicated_id")
                if syndicated_id:
                    log.info("Syndicated_id exist.")
                    # Take syndicated author from the profile or use global config author
                    log.info(
                        "package with name '{0}' already exists. Check creator.".format(
                            updated_package["name"]
                        )
                    )
                    author = (
                        profile["syndicate_author"]
                        if profile and profile.get("syndicate_author", "")
                        else get_syndicated_author()
                    )
                    if author is None:
                        raise
                    try:
                        remote_package = ckan.action.package_show(
                            id=updated_package["name"]
                        )
                        remote_user = ckan.action.user_show(id=author)
                    except toolkit.ValidationError as e:
                        log.error(e.errors)
                        raise
                    except toolkit.ObjectNotFound:
                        log.error('User "{0}" not found'.format(author))
                        raise
                    else:
                        if (
                            remote_package["creator_user_id"]
                            == remote_user["id"]
                        ):
                            log.info(
                                "Author is the same({0}). Updating".format(
                                    author
                                )
                            )

                            ckan.action.package_update(
                                id=remote_package["id"], **updated_package
                            )
                            set_syndicated_id(
                                package,
                                remote_package["id"],
                                profile["syndicate_field_id"]
                                if profile
                                else "",
                            )

                        else:
                            log.info(
                                "Creator of remote package '{0}' did not match '{1}'. Skipping".format(
                                    remote_user["name"], author
                                )
                            )
        except requests.ConnectionError as e:
            log.error("Package update error", exc_info=e)
    except ckanapi.NotFound:
        _create_package(package, profile)


def set_syndicated_id(local_package, remote_package_id, field_id=""):
    """Set the remote package id on the local package"""
    syndicate_field_id = field_id if field_id else get_syndicated_id()

    ext_id = (
        model.Session.query(model.PackageExtra.id)
        .join(model.Package, model.Package.id == model.PackageExtra.package_id)
        .filter(
            model.Package.id == local_package["id"],
            model.PackageExtra.key == syndicate_field_id,
        )
        .first()
    )
    if not ext_id:
        if not toolkit.check_ckan_version("2.9"):
            rev = model.repo.new_revision()
        existing = model.PackageExtra(
            package_id=local_package["id"],
            key=syndicate_field_id,
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


def _update_package_extras(package):
    from ckan.lib.dictization.model_save import package_extras_save

    package_id = package["id"]
    package_obj = model.Package.get(package_id)
    if not package:
        raise Exception("No Package with ID %s found:s" % package_id)

    extra_dicts = package.get("extras")
    context_ = {"model": model, "session": model.Session}
    if not toolkit.check_ckan_version("2.9"):
        rev = model.repo.new_revision()
        rev.author = toolkit.get_action("get_site_user")(
            {"model": model, "ignore_auth": True}, {}
        )["name"]
    package_extras_save(extra_dicts, package_obj, context_)
    model.Session.commit()
    model.Session.flush()

    _update_search_index(package_obj.id, log)


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
