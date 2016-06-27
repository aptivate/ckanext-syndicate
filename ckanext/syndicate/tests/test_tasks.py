from mock import patch

import ckanapi

import ckan.tests.helpers as helpers
import ckan.tests.factories as factories
from ckan.lib.helpers import get_pkg_dict_extra

from ckanext.syndicate.tests.helpers import (
    FunctionalTestBaseClass,
    assert_equal,
    assert_is_not_none,
    test_upload_file,
    _get_context,
)

from ckanext.syndicate.tasks import sync_package, sync_resource


class TestSyncTask(FunctionalTestBaseClass):

    def setup(self):
        super(TestSyncTask, self).setup()
        self.user = factories.User()

    def test_create_package(self):
        context = {
            'user': self.user['name'],
        }

        dataset = helpers.call_action(
            'package_create',
            context=context,
            name='syndicated_dataset',
            extras=[
                {'key': 'syndicate', 'value': 'true'},
            ],
            resources=[{
                'upload': test_upload_file,
                'url': 'test_file.txt',
                'url_type': 'upload',
                'format': 'txt',
                'name': 'test_file.txt',
            }, {
                'upload': test_upload_file,
                'url': 'test_file1.txt',
                'url_type': 'upload',
                'format': 'txt',
                'name': 'test_file1.txt',
            }],
        )
        assert_equal(dataset['name'], 'syndicated_dataset')

        with patch('ckanext.syndicate.tasks.get_target') as mock_target:
            # Mock API
            mock_target.return_value = ckanapi.TestAppCKAN(
                self._get_test_app(), apikey=self.user['apikey'])

            # Syndicate to our Test CKAN instance
            sync_package(dataset['id'], 'dataset/create')

        # Reload our local package, to read the syndicated ID
        source = helpers.call_action(
            'package_show',
            context=context,
            id=dataset['id'],
        )

        # The source package should have a syndicated_id set pointing to the
        # new syndicated package.
        syndicated_id = get_pkg_dict_extra(source, 'syndicated_id')
        assert_is_not_none(syndicated_id)

        # Expect a new package to be created
        syndicated = helpers.call_action(
            'package_show',
            context=context,
            id=syndicated_id,
        )

        # Expect the id of the syndicated package to match the metadata
        # syndicated_id in the source package.
        assert_equal(syndicated['id'], syndicated_id)

        # Test links to resources on the source CKAN instace have been added
        resources = syndicated['resources']
        assert_equal(len(resources), 2)
        remote_resource_url = resources[0]['url']
        local_resource_url = source['resources'][0]['url']
        assert_equal(local_resource_url, remote_resource_url)

        remote_resource_url = resources[1]['url']
        local_resource_url = source['resources'][1]['url']
        assert_equal(local_resource_url, remote_resource_url)

    def test_update_package(self):
        context = {
            'user': self.user['name'],
        }

        # Create a dummy remote dataset
        remote_dataset = helpers.call_action(
            'package_create',
            context=_get_context(context),
            name='remote_dataset',
        )

        syndicated_id = remote_dataset['id']

        # Create the local syndicated dataset, pointing to the dummy remote
        dataset = helpers.call_action(
            'package_create',
            context=_get_context(context),
            name='syndicated_dataset',
            extras=[
                {'key': 'syndicate', 'value': 'true'},
                {'key': 'syndicated_id', 'value': syndicated_id},
            ],
            resources=[{
                'upload': test_upload_file,
                'url': 'test_file.txt',
                'url_type': 'upload',
                'format': 'txt',
                'name': 'test_file.txt',
            },
            ]
        )

        assert_equal(2, len(helpers.call_action('package_list')))

        with patch('ckanext.syndicate.tasks.get_target') as mock_target:
            # Mock API
            mock_target.return_value = ckanapi.TestAppCKAN(
                self._get_test_app(), apikey=self.user['apikey'])

            # Test syncing update
            sync_package(dataset['id'], 'dataset/update')

        # Expect the remote package to be updated
        syndicated = helpers.call_action(
            'package_show',
            context=_get_context(context),
            id=syndicated_id,
        )

        # Expect the id of the syndicated package to match the metadata
        # syndicated_id in the source package.
        assert_equal(syndicated['id'], syndicated_id)

        # Test the local the local resources URL has been updated
        resources = syndicated['resources']
        assert_equal(len(resources), 1)
        remote_resource_url = resources[0]['url']
        local_resource_url = dataset['resources'][0]['url']
        assert_equal(local_resource_url, remote_resource_url)

    def test_syndicate_existing_package(self):
        context = {
            'user': self.user['name'],
        }

        existing = helpers.call_action(
            'package_create',
            context=_get_context(context),
            name='existing-dataset',
            notes='The MapAction PowerPoint Map Pack contains a set of country level reference maps'
        )

        existing['extras'] = [
            {'key': 'syndicate', 'value': 'true'},
        ]

        helpers.call_action(
            'package_update',
            context=_get_context(context),
            **existing)

        with patch('ckanext.syndicate.tasks.get_target') as mock_target:
            mock_target.return_value = ckanapi.TestAppCKAN(
                self._get_test_app(), apikey=self.user['apikey'])

            sync_package(existing['id'], 'dataset/update')

        updated = helpers.call_action(
            'package_show',
            context=_get_context(context),
            id=existing['id'],
        )

        syndicated_id = get_pkg_dict_extra(updated, 'syndicated_id')

        syndicated = helpers.call_action(
            'package_show',
            context=_get_context(context),
            id=syndicated_id,
        )

        # Expect the id of the syndicated package to match the metadata
        # syndicated_id in the source package.
        assert_equal(syndicated['notes'], updated['notes'])

    def test_syndicate_existing_package_with_stale_syndicated_id(self):
        context = {
            'user': self.user['name'],
        }

        existing = helpers.call_action(
            'package_create',
            context=_get_context(context),
            name='existing-dataset',
            notes='The MapAction PowerPoint Map Pack contains a set of country level reference maps',
            extras=[
                {'key': 'syndicate', 'value': 'true'},
                {'key': 'syndicated_id',
                 'value': '87f7a229-46d0-4171-bfb6-048c622adcdc'}
            ]
        )

        with patch('ckanext.syndicate.tasks.get_target') as mock_target:
            mock_target.return_value = ckanapi.TestAppCKAN(
                self._get_test_app(), apikey=self.user['apikey'])

            sync_package(existing['id'], 'dataset/update')

        updated = helpers.call_action(
            'package_show',
            context=_get_context(context),
            id=existing['id'],
        )

        syndicated_id = get_pkg_dict_extra(updated, 'syndicated_id')

        syndicated = helpers.call_action(
            'package_show',
            context=_get_context(context),
            id=syndicated_id,
        )

        assert_equal(syndicated['notes'], updated['notes'])

    def test_delete_package(self):
        context = {
            'user': self.user['name'],
        }

        # Create a dummy remote dataset
        remote_dataset = helpers.call_action(
            'package_create',
            context=_get_context(context),
            name='remote_dataset',
        )

        syndicated_id = remote_dataset['id']

        # Create the local syndicated dataset, pointing to the dummy remote
        dataset = helpers.call_action(
            'package_create',
            context=_get_context(context),
            name='syndicated_dataset',
            extras=[
                {'key': 'syndicate', 'value': 'true'},
                {'key': 'syndicated_id', 'value': syndicated_id},
            ],
        )

        assert_equal(2, len(helpers.call_action('package_list')))

        with patch('ckanext.syndicate.tasks.get_target') as mock_target:
            mock_target.return_value = ckanapi.TestAppCKAN(
                self._get_test_app(), apikey=self.user['apikey'])

            sync_package(dataset['id'], 'dataset/delete')

        remote_dataset = helpers.call_action(
            'package_show',
            context={'ignore_auth': True},
            id=syndicated_id
        )

        assert_equal(remote_dataset['state'], 'deleted')

    def test_add_resource(self):
        context = {
            'user': self.user['name'],
        }

        remote_dataset = helpers.call_action(
            'package_create',
            context=_get_context(context),
            name='remote_dataset',
        )

        syndicated_id = remote_dataset['id']

        # Create the local syndicated dataset, pointing to the dummy remote
        dataset = helpers.call_action(
            'package_create',
            context=_get_context(context),
            name='syndicated_dataset',
            extras=[
                {'key': 'syndicate', 'value': 'true'},
                {'key': 'syndicated_id', 'value': syndicated_id},
            ],
        )

        assert_equal(len(dataset['resources']), 0)

        with patch('ckanext.syndicate.tasks.get_target') as mock_target:
            # Mock API
            mock_target.return_value = ckanapi.TestAppCKAN(
                self._get_test_app(), apikey=self.user['apikey'])

            resource = helpers.call_action(
                'resource_create',
                package_id=dataset['id'],
                upload=test_upload_file,
                url='test_file.txt',
                format='txt',
                name='test_file.txt')

            dataset = helpers.call_action(
                'package_show',
                context=_get_context(context),
                id=dataset['id'])

            # Test syncing update
            sync_resource(dataset['id'], resource['id'], 'resource/create')

        # Expect the remote package to be updated
        syndicated = helpers.call_action(
            'package_show',
            context=_get_context(context),
            id=syndicated_id,
        )

        resources = syndicated['resources']
        assert_equal(len(resources), 1)

        remote_resource_url = resources[0]['url']
        local_resource_url = dataset['resources'][0]['url']

        assert_equal(local_resource_url, remote_resource_url)
