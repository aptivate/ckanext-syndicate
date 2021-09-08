from __future__ import annotations

from typing import Any, Optional
from ckan.plugins import Interface


class ISyndicate(Interface):
    def skip_syndication(self, package: dict[str, Any], flag: str):
        """Decide whether a package must NOT be syndicated.

        Return `True` if package does not need syndication. Keep in mind, that
        non-syndicated package remains the same on the remote side. If package
        was removed locally, it's better not to skip syndication, so that it
        can be removed from the remote side.

        """
        return False

    def prepare_package_for_syndication(
        self, package_id: str, data_dict: dict[str, Any]
    ):
        return data_dict
