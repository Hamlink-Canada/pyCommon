"""Canonical Python regular expressions for shared and Portal validation."""

import re

CALL_SIGN_RE = re.compile(
    r"^[A-Z0-9]{1,3}[0-9][A-Z]{1,4}(?:/(?:P|M|MM|AM|QRP|[A-Z]{1,3}[0-9]))?$",
    re.IGNORECASE,
)
COUNTRY_CODE_RE = re.compile(r"^[A-Z]{2}$")
GRID_SQUARE_RE = re.compile(r"^[A-R]{2}[0-9]{2}(?:[A-X]{2})?$", re.IGNORECASE)
SITE_CODE_RE = re.compile(r"^[2-8][0-9]$")
USER_ID_RE = re.compile(r"^\S(?:.*\S)?$")
