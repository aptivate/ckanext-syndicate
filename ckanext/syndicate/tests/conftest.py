import pytest

from pytest_factoryboy import register

from ckan.tests import factories


@register
class PackageFactory(factories.Dataset):
    pass


@register
class UserFactory(factories.User):
    pass
