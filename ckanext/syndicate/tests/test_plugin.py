from mock import patch

import unittest

import ckan.model as model
from ckan.model.domain_object import DomainObjectOperation

from ckanext.syndicate.plugin import SyndicatePlugin


class TestNotify(unittest.TestCase):
    def setUp(self):
        super(TestNotify, self).setUp()
        self.entity = model.Package()
        self.entity.extras = {'syndicate': 'true'}
        self.syndicate_patch = patch('ckanext.syndicate.plugin.syndicate_task')
        self.plugin = SyndicatePlugin()

    def test_syndicates_task_for_dataset_create(self):
        with self.syndicate_patch as mock_syndicate:
            self.plugin.notify(self.entity, DomainObjectOperation.new)
            mock_syndicate.assert_called_with(self.entity.id,
                                              'dataset/create')

    def test_syndicates_task_for_dataset_update(self):
        with self.syndicate_patch as mock_syndicate:
            self.plugin.notify(self.entity, DomainObjectOperation.changed)
            mock_syndicate.assert_called_with(self.entity.id,
                                              'dataset/update')

    def test_syndicates_task_for_dataset_delete(self):
        with self.syndicate_patch as mock_syndicate:
            self.plugin.notify(self.entity, DomainObjectOperation.deleted)
            mock_syndicate.assert_called_with(self.entity.id,
                                              'dataset/delete')
