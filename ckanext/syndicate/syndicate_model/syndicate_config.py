from sqlalchemy import (
    Table,
    Column,
    UnicodeText,
    Boolean
)
from ckan.model.types import make_uuid
from sqlalchemy.orm.exc import NoResultFound
import ckan.model.meta as meta
from ckan.model.domain_object import DomainObject
import ckan.model as model
from ckanext.syndicate.syndicate_model.model import Base
import ckan.plugins.toolkit as toolkit

class SyndicateConfig(Base, DomainObject):
    __tablename__ = 'syndicate_config'

    id = Column(UnicodeText, primary_key=True, default=make_uuid)
    syndicate_url = Column(UnicodeText, unique=True)
    syndicate_api_key = Column(UnicodeText)
    syndicate_organization = Column(UnicodeText)
    syndicate_flag = Column(UnicodeText)
    syndicate_field_id = Column(UnicodeText)
    syndicate_prefix = Column(UnicodeText)
    syndicate_replicate_organization = Column(Boolean)
    syndicate_author = Column(UnicodeText)

    @classmethod
    def get_syndicate_config(cls):
        pass
