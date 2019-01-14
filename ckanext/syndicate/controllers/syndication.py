import ckan.plugins.toolkit as tk
import ckan.lib.base as base
import ckan.lib.helpers as h
import ckan.logic as logic
import ckan.model as model
from ckan.common import c, request, _

from ckanext.syndicate.syndicate_model.syndicate_profiles import (
    SyndicateProfiles
    )


class SyndicationController(base.BaseController):

    def syndication_profiles(self):
        error = ''
        context = {'model': model, 'session': model.Session,
                   'user': c.user or c.author}
        try:
            logic.check_access('sysadmin', context, {})
        except logic.NotAuthorized:
            base.abort(401, _('Need to be sysadmin to administer'))

        if request.method == 'POST':
            data = request.params
            profiles_suffix_number = [key.split(
                "_")[-1] for key in data if "syndicate_ckan_url" in key
            ]
            collected_profiles = []

            for i in profiles_suffix_number:
                suffix = ("_" + str(i))
                profile_data = {key.replace(
                    suffix, ''): data[key] for key in data if suffix in key}
                collected_profiles.append(profile_data)
            if collected_profiles:
                tk.get_action('syndicate_save_profiles')(
                    context, collected_profiles)
        profiles = tk.get_action('syndicate_get_profiles')({}, {})

        extra_vars = {'profiles': profiles}
        return base.render(
            'admin/syndication_profiles.html',
            extra_vars=extra_vars)
