import os
import uuid

from pylons import config
import ckan.model as model
import ckan.plugins.toolkit as toolkit
import ckan.logic as logic
import ckan.lib.helpers as h

from ckanext.syndicate.syndicate_model.syndicate_profiles import (
    SyndicateProfiles
    )

ValidationError = logic.ValidationError

required_fields = [
    'syndicate_ckan_url', 'syndicate_api_key', 'syndicate_field_id']


def get_actions():
    return dict(
        syndicate_get_profiles=syndicate_get_profiles,
        syndicate_save_profiles=syndicate_save_profiles,
        syndicate_remove_profile=syndicate_remove_profile
    )


def syndicate_get_profiles(context, data_dict):
    profiles = model.Session.query(SyndicateProfiles)
    return profiles.all()


def syndicate_save_profiles(context, data_dict):
    try:
        new_profiles = []
        for profile in data_dict:
            errors = [
                field + ': Missing value!' for field in profile
                if field in required_fields and not profile[field]
            ]

            if errors:
                raise ValidationError(errors)

            if not profile['id']:
                profile['id'] = id = str(uuid.uuid4())
                pf = SyndicateProfiles(**profile)
                new_profiles.append(pf)
            else:
                update_profile = model.Session.query(SyndicateProfiles)\
                    .filter(SyndicateProfiles.id == profile['id'])
                del profile['id']
                update_profile.update(profile)

        if new_profiles:
            model.Session.add_all(new_profiles)
        model.Session.commit()
    except ValidationError as e:
        for err_msg in e.error_dict['message']:
            h.flash_error(err_msg)
        return {'success': False}

    return {'success': True}


def syndicate_remove_profile(context, data_dict):
    prof_id = data_dict.get('id')
    try:
        model.Session.query(SyndicateProfiles)\
            .filter(SyndicateProfiles.id == prof_id)\
            .delete()
        model.Session.commit()
    except Exception as e:
        h.flash_error(e)
        return {'success': False}

    return {'success': True}
