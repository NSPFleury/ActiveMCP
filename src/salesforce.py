"""
Salesforce REST API client.

Wraps the three functional areas required by the MCP server:
  1. Accounts & Contacts  - query
  2. Cases                - query, create, update
  3. Opportunities        - query

All public methods return plain dicts / lists so the MCP layer can
serialize them directly into tool results.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .auth import SalesforceAuth, SalesforceAuthError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RETRYABLE = (requests.exceptions.ConnectionError, requests.exceptions.Timeout)


def _retryable():
    return retry(
        retry=retry_if_exception_type(_RETRYABLE),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(4),
        reraise=True,
    )


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class SalesforceClient:
    """
    Thin REST client for Salesforce.

    Handles:
    - Token injection and automatic refresh on 401.
    - JSON serialisation/deserialisation.
    - Consistent error surfacing via SalesforceAPIError.
    """

    def __init__(self, auth: Optional[SalesforceAuth] = None) -> None:
        self._auth = auth or SalesforceAuth()
        self._session = requests.Session()

    # ------------------------------------------------------------------
    # 1. Accounts & Contacts
    # ------------------------------------------------------------------

    def query_accounts(
        self,
        search: Optional[str] = None,
        fields: Optional[list[str]] = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Query Account records.

        Args:
            search: Optional name filter (case-insensitive LIKE match).
            fields: Fields to return. Defaults to a useful subset.
            limit:  Maximum number of records. Max 200.

        Returns:
            List of Account record dicts.
        """
        default_fields = [
            "Id", "Name", "Phone", "Website",
            "BillingCity", "BillingState", "BillingCountry",
            "Industry", "Type", "OwnerId",
        ]
        selected = ", ".join(fields or default_fields)
        soql = f"SELECT {selected} FROM Account"
        if search:
            escaped = _soql_escape(search)
            soql += f" WHERE Name LIKE '%{escaped}%'"
        soql += f" ORDER BY Name ASC LIMIT {min(limit, 200)}"
        return self._query(soql)

    def query_contacts(
        self,
        search: Optional[str] = None,
        account_id: Optional[str] = None,
        fields: Optional[list[str]] = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Query Contact records.

        Args:
            search:     Optional name/email filter.
            account_id: Optionally restrict to a single Account.
            fields:     Fields to return. Defaults to a useful subset.
            limit:      Maximum number of records. Max 200.

        Returns:
            List of Contact record dicts.
        """
        default_fields = [
            "Id", "FirstName", "LastName", "Email",
            "Phone", "Title", "AccountId", "Account.Name",
            "MailingCity", "MailingState",
        ]
        selected = ", ".join(fields or default_fields)
        soql = f"SELECT {selected} FROM Contact"

        conditions: list[str] = []
        if search:
            escaped = _soql_escape(search)
            conditions.append(
                f"(Name LIKE '%{escaped}%' OR Email LIKE '%{escaped}%')"
            )
        if account_id:
            conditions.append(f"AccountId = '{_soql_escape(account_id)}'")

        if conditions:
            soql += " WHERE " + " AND ".join(conditions)
        soql += f" ORDER BY LastName ASC LIMIT {min(limit, 200)}"
        return self._query(soql)

    # ------------------------------------------------------------------
    # 2. Cases
    # ------------------------------------------------------------------

    def query_cases(
        self,
        status: Optional[str] = None,
        account_id: Optional[str] = None,
        fields: Optional[list[str]] = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Query Case records.

        Args:
            status:     Optional status filter (e.g. 'Open', 'Closed').
            account_id: Optionally restrict to a single Account.
            fields:     Fields to return. Defaults to a useful subset.
            limit:      Maximum number of records. Max 200.

        Returns:
            List of Case record dicts.
        """
        default_fields = [
            "Id", "CaseNumber", "Subject", "Status", "Priority",
            "Origin", "AccountId", "Account.Name",
            "ContactId", "Contact.Name", "OwnerId",
            "CreatedDate", "LastModifiedDate", "Description",
        ]
        selected = ", ".join(fields or default_fields)
        soql = f"SELECT {selected} FROM Case"

        conditions: list[str] = []
        if status:
            conditions.append(f"Status = '{_soql_escape(status)}'")
        if account_id:
            conditions.append(f"AccountId = '{_soql_escape(account_id)}'")

        if conditions:
            soql += " WHERE " + " AND ".join(conditions)
        soql += f" ORDER BY CreatedDate DESC LIMIT {min(limit, 200)}"
        return self._query(soql)

    def create_case(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Create a new Case.

        Args:
            data: Dict of field name -> value. At minimum supply 'Subject'.

        Returns:
            Dict with 'id', 'success', and 'errors' keys from Salesforce.

        Raises:
            SalesforceAPIError: on API-level errors.
        """
        url = f"{self._auth.rest_base_url()}/sobjects/Case"
        return self._post(url, data)

    def update_case(self, case_id: str, data: dict[str, Any]) -> dict[str, str]:
        """
        Update an existing Case.

        Args:
            case_id: The 18-character Salesforce Case Id.
            data:    Dict of field name -> new value.

        Returns:
            Dict with 'id' and 'status' keys.

        Raises:
            SalesforceAPIError: on API-level errors.
        """
        url = f"{self._auth.rest_base_url()}/sobjects/Case/{case_id}"
        self._patch(url, data)
        return {"id": case_id, "status": "updated"}

    # ------------------------------------------------------------------
    # 3. Opportunities
    # ------------------------------------------------------------------

    def query_opportunities(
        self,
        stage: Optional[str] = None,
        account_id: Optional[str] = None,
        fields: Optional[list[str]] = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Query Opportunity records.

        Args:
            stage:      Optional StageName filter (e.g. 'Prospecting').
            account_id: Optionally restrict to a single Account.
            fields:     Fields to return. Defaults to a useful subset.
            limit:      Maximum number of records. Max 200.

        Returns:
            List of Opportunity record dicts.
        """
        default_fields = [
            "Id", "Name", "StageName", "Amount", "CloseDate",
            "Probability", "AccountId", "Account.Name",
            "OwnerId", "Type", "LeadSource",
            "CreatedDate", "LastModifiedDate",
        ]
        selected = ", ".join(fields or default_fields)
        soql = f"SELECT {selected} FROM Opportunity"

        conditions: list[str] = []
        if stage:
            conditions.append(f"StageName = '{_soql_escape(stage)}'")
        if account_id:
            conditions.append(f"AccountId = '{_soql_escape(account_id)}'")

        if conditions:
            soql += " WHERE " + " AND ".join(conditions)
        soql += f" ORDER BY CloseDate ASC LIMIT {min(limit, 200)}"
        return self._query(soql)

    # ------------------------------------------------------------------
    # Low-level HTTP helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return self._auth.auth_headers()

    @_retryable()
    def _query(self, soql: str) -> list[dict[str, Any]]:
        """Execute a SOQL query and return the records list."""
        url = f"{self._auth.rest_base_url()}/query"
        params = {"q": soql}

        logger.debug("SOQL: %s", soql)

        response = self._request_with_token_refresh(
            "GET", url, params=params
        )
        data = response.json()
        return data.get("records", [])

    @_retryable()
    def _post(self, url: str, body: dict[str, Any]) -> dict[str, Any]:
        response = self._request_with_token_refresh("POST", url, json=body)
        return response.json()

    @_retryable()
    def _patch(self, url: str, body: dict[str, Any]) -> None:
        self._request_with_token_refresh("PATCH", url, json=body)

    def _request_with_token_refresh(
        self, method: str, url: str, **kwargs: Any
    ) -> requests.Response:
        """
        Make an HTTP request, transparently refreshing the token on 401.
        """
        response = self._session.request(
            method, url, headers=self._headers(), **kwargs
        )

        if response.status_code == 401:
            logger.info("Received 401 - refreshing Salesforce token")
            self._auth.refresh()
            response = self._session.request(
                method, url, headers=self._headers(), **kwargs
            )

        _raise_for_salesforce_error(response)
        return response


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _soql_escape(value: str) -> str:
    """Escape single quotes in SOQL string literals to prevent injection."""
    return value.replace("'", "\\'")


def _raise_for_salesforce_error(response: requests.Response) -> None:
    """Raise SalesforceAPIError for non-2xx responses."""
    if response.ok:
        return

    # 204 No Content is success for PATCH
    if response.status_code == 204:
        return

    try:
        errors = response.json()
        if isinstance(errors, list) and errors:
            msg = "; ".join(
                f"{e.get('errorCode', '?')}: {e.get('message', '?')}"
                for e in errors
            )
        else:
            msg = str(errors)
    except ValueError:
        msg = response.text

    raise SalesforceAPIError(
        f"Salesforce API error [{response.status_code}]: {msg}",
        status_code=response.status_code,
    )


class SalesforceAPIError(Exception):
    """Raised when the Salesforce REST API returns an error response."""

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code
