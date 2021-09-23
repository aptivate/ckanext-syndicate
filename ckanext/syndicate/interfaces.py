from __future__ import annotations

import logging
from typing import Any
from werkzeug.utils import import_string

import ckan.model as model
import ckan.plugins.toolkit as tk
from ckan.plugins import Interface

from .types import Profile

log = logging.getLogger(__name__)


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
        if package.private:
            return True

        if profile.predicate:
            predicate = import_string(profile.predicate)
            if not predicate(package):
                log.info(
                    "Dataset[{}] will not syndicate because of predicate[{}]"
                    " rejection".format(package.id, profile.predicate)
                )
                return True

        syndicate = tk.asbool(package.extras.get(profile.flag, "false"))
        return not syndicate

    def prepare_package_for_syndication(
        self, package_id: str, data_dict: dict[str, Any], profile: Profile
    ) -> dict[str, Any]:
        """Make modifications of the dict that will be sent to remote portal.

        Remove all the sensitive fields, normalize package type, etc.

        """
        return data_dict
