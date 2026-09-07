import hashlib
import json
from collections.abc import Mapping


def build_etag(parameters: Mapping[str, object], file_revision: str) -> str:
    value = json.dumps(
        {"parameters": parameters, "file_revision": file_revision},
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(value.encode()).hexdigest()
    return f'"{digest}"'


def etag_matches(if_none_match: str | None, current_etag: str) -> bool:
    if not if_none_match:
        return False
    expected = current_etag.removeprefix("W/")
    return any(
        candidate.strip() == "*" or candidate.strip().removeprefix("W/") == expected
        for candidate in if_none_match.split(",")
    )
