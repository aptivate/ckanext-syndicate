from __future__ import annotations

from typing import Any, Optional
from ckan.model.domain_object import DomainObject
from ckan.model.types import make_uuid
import ckan.plugins.toolkit as tk

from sqlalchemy import Column, UnicodeText, Boolean

from ckanext.syndicate.syndicate_model.model import Base


class SyndicateConfig(Base, DomainObject):
    __tablename__ = "syndicate_config"

    id: str = Column(UnicodeText, primary_key=True, default=make_uuid)
    syndicate_ckan_url: str = Column(UnicodeText, unique=True)
    syndicate_api_key: Optional[str] = Column(UnicodeText)
    syndicate_organization: Optional[str] = Column(UnicodeText)
    syndicate_replicate_organization: bool = Column(Boolean)
    syndicate_author: Optional[str] = Column(UnicodeText)
    predicate: Optional[str] = Column(UnicodeText)
    syndicate_field_id: Optional[str] = Column(UnicodeText)
    syndicate_flag: Optional[str] = Column(UnicodeText)
    syndicate_prefix: Optional[str] = Column(UnicodeText)
    extras: dict[str, Any] = {}

    # not added to _for_seed

    @classmethod
    def get_syndicate_config(cls):
        pass

    @classmethod
    def _for_seed(cls, data):
        return cls(
            syndicate_ckan_url=data[0],
            syndicate_api_key=data[1],
            syndicate_organization=data[2],
            syndicate_replicate_organization=tk.asbool(data[3]),
            syndicate_author=data[4],
            predicate=data[5],
            syndicate_field_id=data[6],
            syndicate_flag=data[7],
            syndicate_prefix=data[8],
        )
