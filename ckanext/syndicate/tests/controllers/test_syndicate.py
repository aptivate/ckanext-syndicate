import mock

import ckan.tests.helpers as helpers
import ckan.tests.factories as factories
from ckan.model import Session, TaskStatus

from ckanext.syndicate.controllers.syndicate import (
    _get_tasks,
    _get_task_and_delete,
    _delete_log_item,
)


from ckanext.syndicate.tests.helpers import (
    FunctionalTestBaseClass,
    assert_equal,
)

patch = mock.patch


class TestSyndicateController(FunctionalTestBaseClass):
    def setup(self):
        super(TestSyndicateController, self).setup()
        self.user = factories.User()
        self.local_org = factories.Organization(
            user=self.user, name="local-org"
        )

    def test_get_tasks(self):
        context = {
            "user": self.user["name"],
        }

        # Create dataset
        dataset = helpers.call_action(
            "package_create",
            context=context,
            name="syndicated_dataset1",
            owner_org=self.local_org["id"],
            extras=[],
            resources=[],
        )

        # Create Task Status entry related to dataset
        task_status = TaskStatus(
            entity_id=dataset["id"],
            entity_type="dataset",
            task_type="syndicate",
            key="http://localhost:5050/",
            value=False,
            error="",
            state="dataset/create",
        )

        Session.add(task_status)
        Session.commit()

        # Expect list of 1 entry to be found
        tasks = _get_tasks(self.local_org["id"])
        assert_equal(len(tasks), 1)

        # Expect task was found and remove, removed id equals dataset id
        data_dict = _get_task_and_delete(
            dataset["id"], "http://localhost:5050/"
        )
        assert_equal(data_dict["id"], dataset["id"])

    def test_delete_log_item(self):
        context = {
            "user": self.user["name"],
        }

        # Create dataset
        dataset = helpers.call_action(
            "package_create",
            context=context,
            name="syndicated_dataset1",
            owner_org=self.local_org["id"],
            extras=[],
            resources=[],
        )

        # Create Task Status entry related to dataset
        task_status = TaskStatus(
            entity_id=dataset["id"],
            entity_type="dataset",
            task_type="syndicate",
            key="http://localhost:5050/",
            value=False,
            error="",
            state="dataset/create",
        )

        Session.add(task_status)
        Session.commit()

        # Expect 1 log entry to be removed
        task = _delete_log_item(dataset["id"], "http://localhost:5050/")
        assert_equal(task, 1)
