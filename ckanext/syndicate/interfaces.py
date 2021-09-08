from __future__ import annotations
from ckanext.syndicate.types import Profile

from typing import Any
import ckan.model as model
from ckan.plugins import Interface


class ISyndicate(Interface):
    def skip_syndication(
        self, package: model.Package, profile: Profile
    ) -> bool:
        """Decide whether a package must NOT be syndicated.

        Return `True` if package does not need syndication. Keep in mind, that
        non-syndicated package remains the same on the remote side. If package
        was removed locally, it's better not to skip syndication, so that it
        can be removed from the remote side.

        """
        return False

    def prepare_package_for_syndication(
        self, package_id: str, data_dict: dict[str, Any], profile: Profile
    ) -> dict[str, Any]:
        """Make modifications of the dict that will be sent to remote portal.

        Remove all the sensitive fields, normalize package type, etc.

        """
        return data_dict
