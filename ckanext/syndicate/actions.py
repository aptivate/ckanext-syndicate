import ckan.model as model
import ckan.plugins.toolkit as toolkit

import ckanext.syndicate.utils as utils
from ckanext.syndicate.syndicate_model.syndicate_config import SyndicateConfig


def syndicate_individual_dataset(context, data_dict):
    id, api_key = toolkit.get_or_bust(data_dict, ["id", "api_key"])
    toolkit.check_access("package_update", context, {"id": id})
    profile = (
        model.Session.query(SyndicateConfig)
        .filter_by(syndicate_api_key=api_key)
        .first()
    )
    if profile is None:
        raise toolkit.ValidationError(
            "Incorrect API Key for syndication endpoint"
        )

    pkg_dict = toolkit.get_action("package_show")(context, {"id": id})
    endpoints = pkg_dict.get("syndication_endpoints", [])
    if profile.syndicate_ckan_url not in endpoints:
        raise toolkit.ValidationError(
            "Syndication endpoint not configured for current dataset"
        )

    utils.syndicate_dataset(
        id, "dataset/update", utils.prepare_profile_dict(profile)
    )

    return {}


def syndicate_datasets_by_endpoint(context, data_dict):
    api_key = toolkit.get_or_bust(data_dict, ["api_key"])

    # only sysadmin can perform this action
    toolkit.check_access("config_option_update", context)
    profile = (
        model.Session.query(SyndicateConfig)
        .filter_by(syndicate_api_key=api_key)
        .first()
    )
    if profile is None:
        raise toolkit.ValidationError(
            "Incorrect API Key for syndication endpoint"
        )
    packages = (
        model.Session.query(model.PackageExtra.package_id.distinct())
        .filter_by(key="syndication_endpoints")
        .filter(model.PackageExtra.value.contains(profile.syndicate_ckan_url))
    )
    prepared_profile = utils.prepare_profile_dict(profile)
    for pkg in packages:
        id = pkg[0]
        utils.syndicate_dataset(id, "dataset/update", prepared_profile)

    return {}


def get_actions():
    return dict(
        syndicate_individual_dataset=syndicate_individual_dataset,
        syndicate_datasets_by_endpoint=syndicate_datasets_by_endpoint,
    )
