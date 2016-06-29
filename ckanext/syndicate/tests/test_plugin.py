from mock import patch

import ckan.model as model
from ckan.model.domain_object import DomainObjectOperation
from ckan.tests import factories, helpers

from ckanext.syndicate.plugin import SyndicatePlugin

from ckanext.syndicate.tests.helpers import (
    assert_false,
)


class TestPlugin(helpers.FunctionalTestBase):
    def setup(self):
        super(TestPlugin, self).setup()
        self.plugin = SyndicatePlugin()


class TestNotify(TestPlugin):
    def setup(self):
        super(TestNotify, self).setup()
        dataset = factories.Dataset(extras=[{'key': 'syndicate', 'value': 'true'}])

        self.dataset = model.Package.get(dataset['id'])


class TestDatasetNotify(TestNotify):
    def setup(self):
        super(TestDatasetNotify, self).setup()
        self.syndicate_patch = patch('ckanext.syndicate.plugin.syndicate_dataset')

    def test_syndicates_task_for_create(self):
        with self.syndicate_patch as mock_syndicate:
            self.plugin.notify(self.dataset, DomainObjectOperation.new)
            mock_syndicate.assert_called_with(self.dataset.id,
                                              'dataset/create')

    def test_does_not_syndicate_for_private_dataset(self):
        self.dataset.private = True

        with self.syndicate_patch as mock_syndicate:
            self.plugin.notify(self.dataset, DomainObjectOperation.new)
            assert_false(mock_syndicate.called)

    def test_syndicates_task_for_update(self):
        with self.syndicate_patch as mock_syndicate:
            self.plugin.notify(self.dataset, DomainObjectOperation.changed)
            mock_syndicate.assert_called_with(self.dataset.id,
                                              'dataset/update')

    def test_does_not_syndicate_for_delete(self):
        with self.syndicate_patch as mock_syndicate:
            self.plugin.notify(self.dataset, DomainObjectOperation.deleted)
            assert_false(mock_syndicate.called)


class TestSyndicateFlag(TestPlugin):
    def setup(self):
        super(TestSyndicateFlag, self).setup()
        dataset = factories.Dataset()
        self.dataset = model.Package.get(dataset['id'])

    def test_syndicate_flag_with_capital_t(self):
        self.dataset.extras = {'syndicate': 'True'}

        syndicate_patch = patch('ckanext.syndicate.plugin.syndicate_dataset')

        with syndicate_patch as mock_syndicate:
            self.plugin.notify(self.dataset, DomainObjectOperation.new)
            mock_syndicate.assert_called_with(self.dataset.id,
                                              'dataset/create')

    def test_not_syndicated_when_flag_false(self):
        self.dataset.extras = {'syndicate': 'false'}

        syndicate_patch = patch('ckanext.syndicate.plugin.syndicate_dataset')

        with syndicate_patch as mock_syndicate:
            self.plugin.notify(self.dataset, DomainObjectOperation.new)
            assert_false(mock_syndicate.called)

    def test_not_syndicated_when_flag_missing(self):
        syndicate_patch = patch('ckanext.syndicate.plugin.syndicate_dataset')

        with syndicate_patch as mock_syndicate:
            self.plugin.notify(self.dataset, DomainObjectOperation.new)
            assert_false(mock_syndicate.called)
