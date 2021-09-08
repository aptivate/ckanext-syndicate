from typing_extensions import TypedDict, Literal


class Profile(TypedDict):
    id: str
    syndicate_url: str
    syndicate_api_key: str
    syndicate_organization: str
    syndicate_flag: str
    syndicate_field_id: str
    syndicate_prefix: str
    syndicate_replicate_organization: bool
    syndicate_author: str

    predicate: str


Topic = Literal["dataset/create", "dataset/update"]
