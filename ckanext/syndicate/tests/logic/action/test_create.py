import nose.tools

from mock import patch

import ckan.tests.helpers as helpers
import ckan.tests.factories as factories
import ckanext.syndicate.tests.helpers as custom_helpers


class TestCreateAction(custom_helpers.FunctionalTestBaseClass):

    def setup(self):
        super(TestCreateAction, self).setup()
        self.user = factories.User()

    def test_dataset_create_hook(self):
        with patch('ckanext.syndicate.plugin.syndicate_task') as mock_task:
            dataset = helpers.call_action(
                'package_create',
                context={
                    'user': self.user['name'],
                },
                name='syndicated_dataset',
                extras=[
                    {'key': 'syndicate', 'value': 'true'},
                ],
            )
            nose.tools.assert_equal(dataset['name'], 'syndicated_dataset')
            first_arg = mock_task.call_args[0][0]
            nose.tools.assert_equal(dataset['id'], first_arg)
