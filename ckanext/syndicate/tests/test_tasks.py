# -*- coding: utf-8 -*-

import pytest

import mock

import ckanapi
import ckan.plugins.toolkit as tk
import ckan.tests.helpers as helpers
import ckan.tests.factories as factories
from ckan.lib.helpers import get_pkg_dict_extra
from ckan.model import Session, TaskStatus

from ckanext.syndicate.plugin import get_syndicated_id

from ckanext.syndicate.tests.helpers import (
    test_upload_file,
    _get_context,
)

from ckanext.syndicate import tasks
from ckanext.syndicate.tasks import sync_package

patch = mock.patch


@pytest.mark.usefixtures("clean_db")
class TestSyncTask(object):
    @pytest.mark.ckan_config("ckan.syndicate.name_prefix", "test")
    @pytest.mark.ckan_config("ckan.syndicate.organization", "remote-org")
    def test_create_package(self, app, monkeypatch):
        user = factories.User()

        local_org = factories.Organization(
            users=[{"capacity": "editor", "name": user["id"]}],
            name="local-org",
        )
        remote_org = factories.Organization(
            users=[{"capacity": "editor", "name": user["id"]}],
            name="remote-org",
        )

        context = {
            "user": user["name"],
        }

        dataset = helpers.call_action(
            "package_create",
            context=context,
            name="syndicated_dataset",
            owner_org=local_org["id"],
            extras=[{"key": "syndicate", "value": "true"}],
            resources=[
                {
                    "upload": test_upload_file,
                    "url": "test_file.txt",
                    "url_type": "upload",
                    "format": "txt",
                    "name": "test_file.txt",
                },
                {
                    "upload": test_upload_file,
                    "url": "test_file1.txt",
                    "url_type": "upload",
                    "format": "txt",
                    "name": "test_file1.txt",
                },
            ],
        )
        assert dataset["name"] == "syndicated_dataset"

        ckan = ckanapi.TestAppCKAN(app, user["apikey"])
        monkeypatch.setattr(tasks, "get_target", lambda *args: ckan)
        sync_package(dataset["id"], "dataset/create")

        # Reload our local package, to read the syndicated ID
        source = helpers.call_action(
            "package_show", context=context, id=dataset["id"],
        )

        # The source package should have a syndicated_id set pointing to the
        # new syndicated package.
        syndicated_id = get_pkg_dict_extra(source, "syndicated_id")
        assert syndicated_id is not None

        # Expect a new package to be created
        syndicated = helpers.call_action(
            "package_show", context=context, id=syndicated_id,
        )

        # Expect the id of the syndicated package to match the metadata
        # syndicated_id in the source package.
        assert syndicated["id"] == syndicated_id
        assert syndicated["name"] == "test-syndicated_dataset"
        assert syndicated["owner_org"] == remote_org["id"]

        # Test links to resources on the source CKAN instace have been added
        resources = syndicated["resources"]
        assert len(resources) == 2
        remote_resource_url = resources[0]["url"]
        local_resource_url = source["resources"][0]["url"]
        assert local_resource_url == remote_resource_url

        remote_resource_url = resources[1]["url"]
        local_resource_url = source["resources"][1]["url"]
        assert local_resource_url == remote_resource_url

    @pytest.mark.ckan_config("ckan.syndicate.organization", "remote-org")
    def test_update_package(self, app, monkeypatch):
        user = factories.User()
        context = {
            "user": user["name"],
        }

        remote_org = factories.Organization(
            users=[{"capacity": "editor", "name": user["id"]}],
            name="remote-org",
        )
        # Create a dummy remote dataset
        remote_dataset = helpers.call_action(
            "package_create",
            context=_get_context(context),
            name="remote_dataset",
        )

        syndicated_id = remote_dataset["id"]

        # Create the local syndicated dataset, pointing to the dummy remote
        dataset = helpers.call_action(
            "package_create",
            context=_get_context(context),
            name="syndicated_dataset",
            extras=[
                {"key": "syndicate", "value": "true"},
                {"key": "syndicated_id", "value": syndicated_id},
            ],
            resources=[
                {
                    "upload": test_upload_file,
                    "url": "test_file.txt",
                    "url_type": "upload",
                    "format": "txt",
                    "name": "test_file.txt",
                },
            ],
        )

        assert 2 == len(helpers.call_action("package_list"))

        ckan = ckanapi.TestAppCKAN(app, user["apikey"])
        monkeypatch.setattr(tasks, "get_target", lambda *args: ckan)

        sync_package(dataset["id"], "dataset/update")

        # Expect the remote package to be updated
        syndicated = helpers.call_action(
            "package_show", context=_get_context(context), id=syndicated_id,
        )

        # Expect the id of the syndicated package to match the metadata
        # syndicated_id in the source package.
        assert syndicated["id"] == syndicated_id
        assert syndicated["owner_org"] == remote_org["id"]

        # Test the local the local resources URL has been updated
        resources = syndicated["resources"]
        assert len(resources) == 1
        remote_resource_url = resources[0]["url"]
        local_resource_url = dataset["resources"][0]["url"]
        assert local_resource_url == remote_resource_url

    def test_syndicate_existing_package(self, monkeypatch, app):
        user = factories.User()
        context = {
            "user": user["name"],
        }

        existing = helpers.call_action(
            "package_create",
            context=_get_context(context),
            name="existing-dataset",
            notes=(
                "The MapAction PowerPoint Map Pack contains "
                "a set of country level reference maps"
            ),
        )

        existing["extras"] = [
            {"key": "syndicate", "value": "true"},
        ]

        helpers.call_action(
            "package_update", context=_get_context(context), **existing
        )

        ckan = ckanapi.TestAppCKAN(app, user["apikey"])
        monkeypatch.setattr(tasks, "get_target", lambda *args: ckan)

        sync_package(existing["id"], "dataset/update")

        updated = helpers.call_action(
            "package_show", context=_get_context(context), id=existing["id"],
        )

        syndicated_id = get_pkg_dict_extra(updated, "syndicated_id")

        syndicated = helpers.call_action(
            "package_show", context=_get_context(context), id=syndicated_id,
        )

        # Expect the id of the syndicated package to match the metadata
        # syndicated_id in the source package.
        assert syndicated["notes"] == updated["notes"]

    def test_syndicate_existing_package_with_stale_syndicated_id(
        self, app, monkeypatch
    ):
        user = factories.User()
        context = {
            "user": user["name"],
        }

        existing = helpers.call_action(
            "package_create",
            context=_get_context(context),
            name="existing-dataset",
            notes=(
                "The MapAction PowerPoint Map Pack contains "
                "a set of country level reference maps",
            ),
            extras=[
                {"key": "syndicate", "value": "true"},
                {
                    "key": "syndicated_id",
                    "value": "87f7a229-46d0-4171-bfb6-048c622adcdc",
                },
            ],
        )

        ckan = ckanapi.TestAppCKAN(app, user["apikey"])
        monkeypatch.setattr(tasks, "get_target", lambda *args: ckan)

        sync_package(existing["id"], "dataset/update")

        updated = helpers.call_action(
            "package_show", context=_get_context(context), id=existing["id"],
        )

        syndicated_id = get_pkg_dict_extra(updated, "syndicated_id")

        syndicated = helpers.call_action(
            "package_show", context=_get_context(context), id=syndicated_id,
        )

        assert syndicated["notes"] == updated["notes"]

    @pytest.mark.ckan_config("ckan.syndicate.name_prefix", "test")
    @pytest.mark.ckan_config("ckan.syndicate.replicate_organization", "yes")
    def test_organization_replication(self, app, monkeypatch):
        user = factories.User()
        local_org = factories.Organization(
            users=[{"capacity": "editor", "name": user["id"]}],
            name="local-org",
            title="Local Org",
        )
        context = {
            "user": user["name"],
        }

        dataset = helpers.call_action(
            "package_create",
            context=context,
            name="syndicated_dataset",
            owner_org=local_org["id"],
            extras=[{"key": "syndicate", "value": "true"}],
        )
        assert dataset["name"] == "syndicated_dataset"

        ckan = ckanapi.TestAppCKAN(app, user["apikey"])
        ckan.address = "http://example.com"
        monkeypatch.setattr(tasks, "get_target", lambda *args: ckan)

        # Syndicate to our Test CKAN instance
        mock_org_create = mock.Mock()
        mock_org_show = mock.Mock()
        mock_org_show.side_effect = tk.ObjectNotFound
        mock_org_create.return_value = local_org

        ckan.action.organization_create = mock_org_create
        ckan.action.organization_show = mock_org_show

        sync_package(dataset["id"], "dataset/create")

        mock_org_show.assert_called_once_with(id=local_org["name"])

        assert mock_org_create.called

    @pytest.mark.ckan_config("ckan.syndicate.name_prefix", "test")
    @pytest.mark.ckan_config("ckan.syndicate.author", "test_author")
    def test_author_check(self, app, monkeypatch):
        user = factories.User(name="test_author")
        context = {"user": user["name"]}
        dataset1 = helpers.call_action(
            "package_create",
            context=context,
            name="syndicated_dataset1",
            extras=[{"key": "syndicate", "value": "true"}],
        )

        dataset2 = helpers.call_action(
            "package_create",
            context=context,
            name="syndicated_dataset2",
            extras=[{"key": "syndicate", "value": "true"}],
        )

        mock_user_show = mock.Mock()
        mock_user_show.return_value = user

        ckan = ckanapi.TestAppCKAN(app, user["apikey"])
        ckan.action.user_show = mock_user_show

        def mock_target(*args):
            return ckan

        monkeypatch.setattr(tasks, "get_target", mock_target)

        sync_package(dataset1["id"], "dataset/create")
        helpers.call_action(
            "package_patch",
            id=dataset1["id"],
            extras=[{"key": "syndicate", "value": "true"}],
        )

        sync_package(dataset1["id"], "dataset/update")
        mock_user_show.assert_called_once_with(id="test_author")
        updated1 = helpers.call_action("package_show", id=dataset1["id"])
        assert get_pkg_dict_extra(updated1, get_syndicated_id()) is not None

        mock_user_show = mock.Mock()
        mock_user_show.return_value = {"name": "random-name", "id": ""}
        ckan.action.user_show = mock_user_show

        sync_package(dataset2["id"], "dataset/create")
        helpers.call_action(
            "package_patch",
            id=dataset2["id"],
            extras=[{"key": "syndicate", "value": "true"}],
        )
        sync_package(dataset2["id"], "dataset/update")
        updated2 = helpers.call_action("package_show", id=dataset2["id"])
        assert not get_pkg_dict_extra(updated2, get_syndicated_id())
        try:
            del Session.revision
        except AttributeError:
            pass
