"""Independent per-message sender overrides with explicit inheritance semantics."""

from dataclasses import dataclass
from enum import StrEnum


class ProfileChoice(StrEnum):
    """INHERIT consults the parent; ORIGINAL stops resolution and omits the override."""

    INHERIT = "inherit"
    ORIGINAL = "original"
    CUSTOM = "custom"


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

    def resolve(fields: tuple[ProfileField, ...]) -> str | None:
        for field in fields:
            if field.choice == ProfileChoice.ORIGINAL:
                return None
            if field.choice == ProfileChoice.CUSTOM:
                return field.value
        return None

    return resolve((library.username, webhook.username, global_profile.username)), resolve(
        (library.avatar_url, webhook.avatar_url, global_profile.avatar_url)
    )
