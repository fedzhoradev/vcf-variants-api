from dataclasses import dataclass
from enum import StrEnum


class MediaType(StrEnum):
    JSON = "application/json"
    XML = "application/xml"


class NotAcceptableError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class _MediaRange:
    value: str
    quality: float
    position: int


def negotiate_content_type(accept: str | None) -> MediaType:
    if accept is None or not accept.strip():
        return MediaType.JSON

    ranges: list[_MediaRange] = []
    for position, raw_item in enumerate(accept.split(",")):
        parts = [part.strip() for part in raw_item.split(";")]
        value = parts[0].lower()
        quality = 1.0
        for parameter in parts[1:]:
            name, separator, raw_value = parameter.partition("=")
            if separator and name.strip().lower() == "q":
                try:
                    quality = float(raw_value)
                except ValueError:
                    quality = 0.0
        if not 0 <= quality <= 1:
            quality = 0.0
        ranges.append(_MediaRange(value=value, quality=quality, position=position))

    candidates: list[tuple[float, int, int, int, MediaType]] = []
    for preference, media_type in enumerate(MediaType):
        matches = [
            (
                2 if item.value == media_type else 1 if item.value == "application/*" else 0,
                -item.position,
                item.quality,
            )
            for item in ranges
            if item.value in {media_type, "application/*", "*/*"}
        ]
        if matches:
            specificity, position, quality = max(matches)
            if quality > 0:
                candidates.append((quality, specificity, position, -preference, media_type))

    if not candidates:
        raise NotAcceptableError("Only application/json and application/xml are supported")
    return max(candidates)[-1]
