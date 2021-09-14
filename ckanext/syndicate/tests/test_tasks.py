# -*- coding: utf-8 -*-

import ckan.tests.factories as factories
import ckan.tests.helpers as helpers
import ckanapi
import mock
import pytest
from ckan.lib.helpers import get_pkg_dict_extra

from ckanext.syndicate.types import Topic
from ckanext.syndicate.utils import get_syndicate_profiles


def _get_context(context):
    from ckan import model

    return {
        "model": context.get("model", model),
        "session": context.get("session", model.Session),
        "user": context.get("user"),
        "ignore_auth": context.get("ignore_auth", False),
    }


from ckanext.syndicate import tasks
from ckanext.syndicate.tasks import sync_package


@pytest.fixture
def ckan(user, app, monkeypatch):
    ckan = ckanapi.TestAppCKAN(app, user["apikey"])
    monkeypatch.setattr(tasks, "get_target", lambda *args: ckan)
    yield ckan


@pytest.mark.usefixtures("clean_db")
class TestSyncTask(object):
    @pytest.mark.ckan_config("ckan.syndicate.name_prefix", "test")
    @pytest.mark.ckan_config("ckan.syndicate.organization", "remote-org")
    def test_create_package(self, ckan, user, create_with_upload):
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
        )
        create_with_upload("test", "test_file.txt", package_id=dataset["id"])
        create_with_upload("test", "test_file1.txt", package_id=dataset["id"])

        assert dataset["name"] == "syndicated_dataset"

        sync_package(
            dataset["id"], Topic.create, next(get_syndicate_profiles())
        )

        # Reload our local package, to read the syndicated ID
        source = helpers.call_action(
            "package_show",
            context=context,
            id=dataset["id"],
        )

        # The source package should have a syndicated_id set pointing to the
        # new syndicated package.
        syndicated_id = get_pkg_dict_extra(source, "syndicated_id")
        assert syndicated_id is not None

        # Expect a new package to be created
        syndicated = helpers.call_action(
            "package_show",
            context=context,
            id=syndicated_id,
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
    def test_update_package(self, user, ckan, create_with_upload):
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
        )
        local_resource = create_with_upload(
            "test", "test_file.txt", package_id=dataset["id"]
        )

        assert 2 == len(helpers.call_action("package_list"))

        sync_package(
            dataset["id"], Topic.update, next(get_syndicate_profiles())
        )

        # Expect the remote package to be updated
        syndicated = helpers.call_action(
            "package_show",
            context=_get_context(context),
            id=syndicated_id,
        )

        # Expect the id of the syndicated package to match the metadata
        # syndicated_id in the source package.
        assert syndicated["id"] == syndicated_id
        assert syndicated["owner_org"] == remote_org["id"]

        # Test the local the local resources URL has been updated
        resources = syndicated["resources"]
        assert len(resources) == 1
        remote_resource_url = resources[0]["url"]
        local_resource_url = local_resource["url"]
        assert local_resource_url == remote_resource_url

    def test_syndicate_existing_package(self, user, ckan):
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

        sync_package(
            existing["id"], Topic.update, next(get_syndicate_profiles())
        )

        updated = helpers.call_action(
            "package_show",
            context=_get_context(context),
            id=existing["id"],
        )

        syndicated_id = get_pkg_dict_extra(updated, "syndicated_id")

        syndicated = helpers.call_action(
            "package_show",
            context=_get_context(context),
            id=syndicated_id,
        )

        # Expect the id of the syndicated package to match the metadata
        # syndicated_id in the source package.
        assert syndicated["notes"] == updated["notes"]

    def test_syndicate_existing_package_with_stale_syndicated_id(
        self, user, ckan
    ):
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

        sync_package(
            existing["id"], Topic.update, next(get_syndicate_profiles())
        )

        updated = helpers.call_action(
            "package_show",
            context=_get_context(context),
            id=existing["id"],
        )

        syndicated_id = get_pkg_dict_extra(updated, "syndicated_id")

        syndicated = helpers.call_action(
            "package_show",
            context=_get_context(context),
            id=syndicated_id,
        )

        assert syndicated["notes"] == updated["notes"]

    @pytest.mark.ckan_config("ckan.syndicate.name_prefix", "test")
    @pytest.mark.ckan_config("ckan.syndicate.replicate_organization", "yes")
    def test_organization_replication(self, user, ckan):
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

        ckan.address = "http://example.com"

        # Syndicate to our Test CKAN instance
        mock_org_create = mock.Mock()
        mock_org_show = mock.Mock()
        mock_org_show.side_effect = ckanapi.NotFound
        mock_org_create.return_value = local_org

        ckan.action.organization_create = mock_org_create
        ckan.action.organization_show = mock_org_show

        sync_package(
            dataset["id"], Topic.create, next(get_syndicate_profiles())
        )

        mock_org_show.assert_called_once_with(id=local_org["name"])

        assert mock_org_create.called

    @pytest.mark.ckan_config("ckan.syndicate.name_prefix", "test")
    def test_author_check(self, user, ckan, monkeypatch, ckan_config):
        monkeypatch.setitem(ckan_config, "ckan.syndicate.author", user["name"])

        context = {"user": user["name"]}
        dataset1 = helpers.call_action(
            "package_create",
            context=context,
            name="syndicated_dataset1",
            extras=[{"key": "syndicate", "value": "true"}],
        )

        mock_user_show = mock.Mock()
        mock_user_show.return_value = user

        ckan.action.user_show = mock_user_show

        profile = next(get_syndicate_profiles())
        sync_package(dataset1["id"], Topic.create, profile)
        helpers.call_action(
            "package_patch",
            id=dataset1["id"],
            extras=[{"key": "syndicate", "value": "true"}],
        )

        sync_package(dataset1["id"], Topic.update, profile)
        mock_user_show.assert_called_once_with(id=user["name"])
        updated1 = helpers.call_action("package_show", id=dataset1["id"])
        assert get_pkg_dict_extra(updated1, "syndicated_id") is not None
