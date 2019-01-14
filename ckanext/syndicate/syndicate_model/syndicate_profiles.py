from sqlalchemy import (
    UnicodeText,
    ForeignKey,
    Column,
    Boolean,
    DateTime
)
import datetime
from ckanext.syndicate.syndicate_model.model import Base


class SyndicateProfiles(Base):
    __tablename__ = 'syndicate_profiles'

    id = Column(UnicodeText, primary_key=True)
    syndicate_ckan_url = Column(UnicodeText)
    syndicate_api_key = Column(UnicodeText)
    syndicate_field_id = Column(UnicodeText)
    syndicate_flag = Column(UnicodeText)
    syndicate_name_prefix = Column(UnicodeText)
    syndicate_author = Column(UnicodeText)
    syndicate_organization = Column(UnicodeText)
    syndicate_replicate_organization = Column(UnicodeText)

    def __repr__(self):
        return '<SyndicateProfile: id={0}, syndicate_ckan_url={1}>'.format(
            self.id, self.syndicate_ckan_url
        )
