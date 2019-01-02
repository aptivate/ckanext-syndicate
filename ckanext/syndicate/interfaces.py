# encoding: utf-8
from ckan.plugins import Interface


class ISyndication(Interface):
    u"""
    Hook for Syndication process.
    """

    def before_syndication_create(self, pkg_dict, package_id):
        u"""Return updated dict before package creation process.
        """

        return pkg_dict

    def before_syndication_update(self, pkg_dict, package_id):
        u"""Return updated dict before package update process.
        """
        return pkg_dict
