# -*- coding: utf-8 -*-

import ckan.plugins.toolkit as tk


CONFIG_ALLOWED_ORG = "ckanext.syndication.predicate.allowed_organization"
CONFIG_DENIED_ORG = "ckanext.syndication.predicate.denied_organization"


def organization_owns_dataset(pkg, conf_name=CONFIG_ALLOWED_ORG):
    orgs = pkg.get_groups("organization")
    if not orgs:
        return False
    title = orgs[0].title
    return title == tk.config.get(conf_name)


def organization_not_owns_dataset(pkg):
    return not organization_owns_dataset(pkg, CONFIG_DENIED_ORG)
