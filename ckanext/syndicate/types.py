from __future__ import annotations

from typing import Any, NamedTuple
from typing_extensions import Literal

Topic = Literal["dataset/create", "dataset/update"]


class Profile(NamedTuple):
    id: str
    ckan_url: str = ""
    api_key: str = ""
    organization: str = ""
    flag: str = "syndicate"
    field_id: str = "syndicated_id"
    name_prefix: str = ""
    replicate_organization: bool = False
    author: str = ""

    predicate: str = ""
    extras: dict[str, Any] = {}
