"""
Salesforce OAuth 2.0 - Username-Password Flow

Exchanges Salesforce credentials for a bearer token and instance URL.
Tokens are cached in-process and refreshed automatically on expiry/401.

Environment variables (loaded from .env):
    SF_CONSUMER_KEY      Connected App consumer key
    SF_CONSUMER_SECRET   Connected App consumer secret
    SF_USERNAME          Salesforce username
    SF_PASSWORD          Salesforce user password
    SF_SECURITY_TOKEN    Salesforce security token (appended to password)
    SF_DOMAIN            'login' (prod) or 'test' (sandbox). Default: 'login'
    SF_API_VERSION       Salesforce API version. Default: 'v59.0'
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import requests
from dotenv import load_dotenv
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_REQUIRED_ENV_VARS = (
    "SF_CONSUMER_KEY",
    "SF_CONSUMER_SECRET",
    "SF_USERNAME",
    "SF_PASSWORD",
    "SF_SECURITY_TOKEN",
)


def _get_env(key: str, default: Optional[str] = None) -> str:
    value = os.getenv(key, default)
    if value is None:
        raise EnvironmentError(
            f"Missing required environment variable: {key}. "
            "Copy .env.example to .env and fill in your credentials."
        )
    return value


# ---------------------------------------------------------------------------
# Token dataclass
# ---------------------------------------------------------------------------


@dataclass
class SalesforceToken:
    """Holds a live Salesforce access token and its metadata."""

    access_token: str
    instance_url: str
    token_type: str
    issued_at: float = field(default_factory=time.time)
    # Salesforce tokens don't carry an explicit TTL; we treat them as valid
    # until a 401 is received from the API, at which point the client calls
    # SalesforceAuth.refresh().
    _ttl_seconds: int = field(default=3600, repr=False)

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.issued_at) >= self._ttl_seconds

    @property
    def auth_header(self) -> str:
        return f"{self.token_type} {self.access_token}"


# ---------------------------------------------------------------------------
# Auth class
# ---------------------------------------------------------------------------


class SalesforceAuth:
    """
    Manages Salesforce authentication via the Username-Password OAuth 2.0 flow.

    Usage::

        auth = SalesforceAuth()
        token = auth.get_token()          # cached
        token = auth.refresh()            # force new token
        headers = auth.auth_headers()     # ready-to-use dict
    """

    TOKEN_ENDPOINT = "https://{domain}.salesforce.com/services/oauth2/token"

    def __init__(self) -> None:
        self._consumer_key = _get_env("SF_CONSUMER_KEY")
        self._consumer_secret = _get_env("SF_CONSUMER_SECRET")
        self._username = _get_env("SF_USERNAME")
        # Password and security token are concatenated as required by the flow.
        self._password = _get_env("SF_PASSWORD") + _get_env("SF_SECURITY_TOKEN")
        self._domain = os.getenv("SF_DOMAIN", "login")
        self._api_version = os.getenv("SF_API_VERSION", "v59.0")
        self._token: Optional[SalesforceToken] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_token(self) -> SalesforceToken:
        """Return the cached token, fetching a new one if needed."""
        if self._token is None or self._token.is_expired:
            self._token = self._fetch_token()
        return self._token

    def refresh(self) -> SalesforceToken:
        """Force-fetch a new token regardless of cache state."""
        self._token = self._fetch_token()
        return self._token

    def auth_headers(self) -> dict[str, str]:
        """Return HTTP headers ready for use with requests."""
        token = self.get_token()
        return {
            "Authorization": token.auth_header,
            "Content-Type": "application/json",
        }

    @property
    def instance_url(self) -> str:
        return self.get_token().instance_url

    @property
    def api_version(self) -> str:
        return self._api_version

    def rest_base_url(self) -> str:
        """Base URL for Salesforce REST API calls."""
        return f"{self.instance_url}/services/data/{self._api_version}"

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @retry(
        retry=retry_if_exception_type(requests.exceptions.ConnectionError),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def _fetch_token(self) -> SalesforceToken:
        """
        Perform the Username-Password OAuth flow against Salesforce.

        Raises:
            EnvironmentError: if required env vars are missing.
            SalesforceAuthError: if Salesforce returns an error response.
            requests.HTTPError: on unexpected HTTP failures.
        """
        url = self.TOKEN_ENDPOINT.format(domain=self._domain)
        payload = {
            "grant_type": "password",
            "client_id": self._consumer_key,
            "client_secret": self._consumer_secret,
            "username": self._username,
            "password": self._password,
        }

        logger.debug("Fetching Salesforce OAuth token from %s", url)

        response = requests.post(url, data=payload, timeout=30)

        if not response.ok:
            try:
                error_body = response.json()
                error_code = error_body.get("error", "unknown_error")
                error_description = error_body.get("error_description", response.text)
            except ValueError:
                error_code = "parse_error"
                error_description = response.text

            raise SalesforceAuthError(
                f"OAuth token request failed [{response.status_code}] "
                f"{error_code}: {error_description}"
            )

        data = response.json()
        token = SalesforceToken(
            access_token=data["access_token"],
            instance_url=data["instance_url"],
            token_type=data.get("token_type", "Bearer"),
            issued_at=float(data.get("issued_at", time.time() * 1000)) / 1000,
        )

        logger.info(
            "Salesforce token acquired for %s (instance: %s)",
            self._username,
            token.instance_url,
        )
        return token


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class SalesforceAuthError(Exception):
    """Raised when Salesforce returns an authentication error."""
