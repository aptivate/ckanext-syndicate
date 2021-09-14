from __future__ import annotations

import enum
from typing import Any, NamedTuple


class Topic(enum.Enum):
    create = enum.auto()
    update = enum.auto()
    unknown = enum.auto()


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
