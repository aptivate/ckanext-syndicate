from mock import patch

import unittest

import ckan.model as model
from ckan.model.domain_object import DomainObjectOperation

from ckanext.syndicate.plugin import SyndicatePlugin


class TestPlugin(unittest.TestCase):
    def test_notify_syndicates_task(self):
        entity = model.Package()
        entity.extras = {'syndicate': 'true'}

        with patch('ckanext.syndicate.plugin.syndicate_task') as mock_syndicate:
            plugin = SyndicatePlugin()

            plugin.notify(entity, DomainObjectOperation.new)
            mock_syndicate.assert_called_with(entity.id, 'dataset/create')
