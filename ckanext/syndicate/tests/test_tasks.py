import nose.tools

from pylons import config

from mock import patch

import ckanapi

import ckan.tests.helpers as helpers
import ckan.tests.factories as factories
from ckan.lib.helpers import get_pkg_dict_extra
import ckanext.syndicate.tests.helpers as custom_helpers

from ckanext.syndicate.tasks import sync_package


class TestSyncPackageTask(custom_helpers.FunctionalTestBaseClass):

    def setup(self):
        super(TestSyncPackageTask, self).setup()
        self.user = factories.User()

    def test_create_new_package(self):
        context={
            'user': self.user['name'],
        }
        dataset = helpers.call_action(
            'package_create',
            context=context,
            name='syndicated_dataset',
            extras=[
                {'key': 'syndicate', 'value': 'true'},
            ],
        )
        nose.tools.assert_equal(dataset['name'], 'syndicated_dataset')

        with patch('ckanext.syndicate.tasks.get_target') as mock_target:
            # Mock API
            mock_target.return_value = ckanapi.TestAppCKAN(
                    self.app, apikey=self.user['apikey'])

            # Syndicate to our Test CKAN instance
            sync_package(dataset['id'], "foo")

        # Reload our local package, to read the syndicated ID
        source = helpers.call_action(
            'package_show',
            context=context,
            id=dataset['id'],
        )

        # The source package should have a syndicated_id set pointing to the
        # new syndicated package.
        syndicated_id = get_pkg_dict_extra(source, 'syndicated_id')
        nose.tools.assert_is_not_none(syndicated_id)

        # Expect a new package to be created
        syndicated = helpers.call_action(
            'package_show',
            context=context,
            id=syndicated_id,
        )

        # Expect the id of the syndicated package to match the metadata
        # syndicated_id in the source package.
        nose.tools.assert_equal(syndicated['id'], syndicated_id)
