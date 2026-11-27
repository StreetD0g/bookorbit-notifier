"""Independent per-message sender overrides with explicit inheritance semantics."""

from dataclasses import dataclass
from enum import StrEnum


class ProfileChoice(StrEnum):
    """INHERIT consults the parent; ORIGINAL stops resolution and omits the override."""

    INHERIT = "inherit"
    ORIGINAL = "original"
    CUSTOM = "custom"
    LOGO = "logo"


# The pinned public PNG is immutable and can be fetched by Discord without
# exposing or requiring a publicly reachable BookOrbit installation.
BUNDLED_LOGO_URL = (
    "https://raw.githubusercontent.com/StreetD0g/bookorbit-notifier/"
    "19c9808e021434272744953256bc5362febba198/backend/app/static/notifier-logo.png"
)


@dataclass(frozen=True, slots=True)
class ProfileField:
    """One independently configured sender field at one scope."""

    choice: ProfileChoice = ProfileChoice.INHERIT
    value: str | None = None

    def __post_init__(self) -> None:
        if self.choice == ProfileChoice.CUSTOM and (self.value is None or not self.value.strip()):
            raise ValueError("Custom sender field must not be empty")
        if self.choice != ProfileChoice.CUSTOM and self.value is not None:
            raise ValueError("Only custom sender fields may have a value")


@dataclass(frozen=True, slots=True)
class SenderProfile:
    """A scope's name and avatar can each inherit or override independently."""

    username: ProfileField = ProfileField()
    avatar_url: ProfileField = ProfileField()


DEFAULT_PROFILE = SenderProfile(username=ProfileField(ProfileChoice.CUSTOM, "BookOrbit Notifier"))


def resolve_profile(
    library: SenderProfile = SenderProfile(),
    webhook: SenderProfile = SenderProfile(),
    global_profile: SenderProfile = DEFAULT_PROFILE,
) -> tuple[str | None, str | None]:
    """Resolve each field from most specific to global; None means Discord's original."""

    def resolve(fields: tuple[ProfileField, ...], *, avatar: bool = False) -> str | None:
        for field in fields:
            if field.choice == ProfileChoice.ORIGINAL:
                return None
            if field.choice == ProfileChoice.CUSTOM:
                return field.value
            if field.choice == ProfileChoice.LOGO:
                if not avatar:
                    raise ValueError("Bundled logo is only valid for avatars")
                return BUNDLED_LOGO_URL
        return None

    return resolve((library.username, webhook.username, global_profile.username)), resolve(
        (library.avatar_url, webhook.avatar_url, global_profile.avatar_url), avatar=True
    )
