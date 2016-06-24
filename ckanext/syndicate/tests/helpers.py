import os
import cgi

import nose.tools

import ckan.tests.helpers as helpers
import ckan.plugins as plugins


from StringIO import StringIO

test_file = StringIO()
test_file.name = 'test_file.txt'
test_file.write('test')

assert_equal = nose.tools.assert_equal
assert_false = nose.tools.assert_false
assert_is_not_none = nose.tools.assert_is_not_none
assert_raises = nose.tools.assert_raises
assert_regexp_matches = nose.tools.assert_regexp_matches
assert_true = nose.tools.assert_true


class UploadLocalFileStorage(cgi.FieldStorage):
    def __init__(self, fp, *args, **kwargs):
        self.name = fp.name
        self.filename = fp.name
        self.file = fp

test_upload_file = UploadLocalFileStorage(test_file)


def fixture_path(path):
    path = os.path.join(os.path.split(__file__)[0], 'test-data', path)
    return os.path.abspath(path)


def _get_context(context):
    from ckan import model
    return {
        'model': context.get('model', model),
        'session': context.get('session', model.Session),
        'user': context.get('user'),
        'ignore_auth': context.get('ignore_auth', False)
    }


class FunctionalTestBaseClass(helpers.FunctionalTestBase):
    @classmethod
    def setup_class(cls):
        super(FunctionalTestBaseClass, cls).setup_class()
        plugins.load('syndicate')

    @classmethod
    def teardown_class(cls):
        plugins.unload('syndicate')
        super(FunctionalTestBaseClass, cls).teardown_class()
