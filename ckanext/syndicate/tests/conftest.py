import pytest
from ckan.tests import factories
from pytest_factoryboy import register


@register
class PackageFactory(factories.Dataset):
    pass


@register
class UserFactory(factories.User):
    pass
