from __future__ import annotations

from typing import Any
from typing_extensions import TypedDict, Literal


class Profile(TypedDict):
    id: str
    url: str
    api_key: str
    organization: str
    flag: str
    field_id: str
    prefix: str
    replicate_organization: bool
    author: str

    predicate: str
    extras: dict[str, Any]


Topic = Literal["dataset/create", "dataset/update"]
