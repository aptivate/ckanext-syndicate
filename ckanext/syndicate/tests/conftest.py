import pytest

from ckanext.syndicate import utils


@pytest.fixture
def clean_db(reset_db):
    reset_db()
    utils.create_db()
