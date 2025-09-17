"""
Utility functions for creating URL-friendly slugs.
"""
import re
import unicodedata


def slugify(text: str, max_length: int = 50, allow_unicode: bool = False) -> str:
    """
    Convert to ASCII if 'allow_unicode' is False. Convert spaces to hyphens.
    Remove characters that aren't alphanumerics, underscores, or hyphens.
    Convert to lowercase. Also strip leading and trailing whitespace.
    """
    if allow_unicode:
        value = text
    else:
        value = unicodedata.normalize('NFKD', text)
        value = value.encode('ascii', 'ignore').decode('ascii')

    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    value = re.sub(r'[-\s]+', '-', value)

    # Truncate to max length
    if len(value) > max_length:
        value = value[:max_length].rstrip('-')

    return value


def make_unique_slug(base_slug: str, existing_slugs: list) -> str:
    """
    Generate a unique slug by appending a number if necessary.
    """
    if base_slug not in existing_slugs:
        return base_slug

    counter = 1
    while f"{base_slug}-{counter}" in existing_slugs:
        counter += 1

    return f"{base_slug}-{counter}"