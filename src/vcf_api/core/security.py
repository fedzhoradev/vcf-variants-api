from hmac import compare_digest


def has_valid_secret(provided: str | None, expected: str) -> bool:
    return provided is not None and compare_digest(
        provided.encode("utf-8"), expected.encode("utf-8")
    )
