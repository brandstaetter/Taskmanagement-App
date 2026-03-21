import hashlib
from urllib.parse import urlencode


def gravatar_url(email: str, size: int = 80, default: str = "identicon") -> str:
    """Generate a Gravatar image URL for the given email address.

    Uses SHA256 hashing as recommended by the Gravatar API.

    Args:
        email: The user's email address.
        size: Avatar size in pixels (1-2048).
        default: Default image style when no Gravatar exists.
            Options: 404, mp, identicon, monsterid, wavatar, retro, robohash, blank.
    """
    normalized = email.strip().lower()
    email_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    params = urlencode({"s": str(size), "d": default})
    return f"https://www.gravatar.com/avatar/{email_hash}?{params}"
