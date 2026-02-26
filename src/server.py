"""
Salesforce MCP Server

Exposes Salesforce data operations as MCP tools that any MCP-compatible
host (Claude Desktop, etc.) can discover and call.

Tools provided:
  - query_accounts        Search / list Salesforce Account records
  - query_contacts        Search / list Salesforce Contact records
  - query_cases           Search / list Salesforce Case records
  - create_case           Create a new Salesforce Case
  - update_case           Update fields on an existing Salesforce Case
  - query_opportunities   Search / list Salesforce Opportunity records

Run:
    python -m src.server            # stdio transport (default for MCP hosts)
    python src/server.py            # same
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any, Optional

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions

from .auth import SalesforceAuth, SalesforceAuthError
from .salesforce import SalesforceAPIError, SalesforceClient

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Server bootstrap
# ---------------------------------------------------------------------------

server = Server("salesforce-mcp")

# Lazy-initialised client (avoids hitting Salesforce at import time).
_client: Optional[SalesforceClient] = None


def _get_client() -> SalesforceClient:
    global _client
    if _client is None:
        _client = SalesforceClient(SalesforceAuth())
    return _client


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

_TOOLS: list[types.Tool] = [
    types.Tool(
        name="query_accounts",
        description=(
            "Search or list Salesforce Account records. "
            "Optionally filter by name and specify which fields to return."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "search": {
                    "type": "string",
                    "description": "Optional name substring to filter accounts (case-insensitive).",
                },
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "List of API field names to return. "
                        "Defaults to: Id, Name, Phone, Website, BillingCity, "
                        "BillingState, BillingCountry, Industry, Type, OwnerId."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of records to return (1-200). Default 20.",
                    "minimum": 1,
                    "maximum": 200,
                    "default": 20,
                },
            },
        },
    ),
    types.Tool(
        name="query_contacts",
        description=(
            "Search or list Salesforce Contact records. "
            "Optionally filter by name/email or restrict to a specific Account."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "search": {
                    "type": "string",
                    "description": "Optional name or email substring filter (case-insensitive).",
                },
                "account_id": {
                    "type": "string",
                    "description": "Salesforce Account Id to restrict contacts to.",
                },
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "List of API field names to return. "
                        "Defaults to: Id, FirstName, LastName, Email, Phone, "
                        "Title, AccountId, Account.Name, MailingCity, MailingState."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of records to return (1-200). Default 20.",
                    "minimum": 1,
                    "maximum": 200,
                    "default": 20,
                },
            },
        },
    ),
    types.Tool(
        name="query_cases",
        description=(
            "Search or list Salesforce Case records. "
            "Optionally filter by status or Account Id."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Case status to filter on (e.g. 'Open', 'Closed', 'New').",
                },
                "account_id": {
                    "type": "string",
                    "description": "Salesforce Account Id to restrict cases to.",
                },
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "List of API field names to return. "
                        "Defaults to: Id, CaseNumber, Subject, Status, Priority, "
                        "Origin, AccountId, Account.Name, ContactId, Contact.Name, "
                        "OwnerId, CreatedDate, LastModifiedDate, Description."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of records to return (1-200). Default 20.",
                    "minimum": 1,
                    "maximum": 200,
                    "default": 20,
                },
            },
        },
    ),
    types.Tool(
        name="create_case",
        description=(
            "Create a new Salesforce Case. "
            "Returns the new Case Id on success."
        ),
        inputSchema={
            "type": "object",
            "required": ["subject"],
            "properties": {
                "subject": {
                    "type": "string",
                    "description": "Case subject (required).",
                },
                "description": {
                    "type": "string",
                    "description": "Detailed case description.",
                },
                "status": {
                    "type": "string",
                    "description": "Initial status (e.g. 'New'). Default: 'New'.",
                },
                "priority": {
                    "type": "string",
                    "description": "Priority: 'High', 'Medium', or 'Low'. Default: 'Medium'.",
                },
                "origin": {
                    "type": "string",
                    "description": "Case origin (e.g. 'Phone', 'Email', 'Web').",
                },
                "account_id": {
                    "type": "string",
                    "description": "Salesforce Account Id to associate the case with.",
                },
                "contact_id": {
                    "type": "string",
                    "description": "Salesforce Contact Id to associate the case with.",
                },
                "extra_fields": {
                    "type": "object",
                    "description": "Any additional Case field/value pairs to set.",
                },
            },
        },
    ),
    types.Tool(
        name="update_case",
        description=(
            "Update one or more fields on an existing Salesforce Case. "
            "The Case Id must be provided."
        ),
        inputSchema={
            "type": "object",
            "required": ["case_id"],
            "properties": {
                "case_id": {
                    "type": "string",
                    "description": "18-character Salesforce Case Id.",
                },
                "subject": {
                    "type": "string",
                    "description": "New subject text.",
                },
                "description": {
                    "type": "string",
                    "description": "Updated description.",
                },
                "status": {
                    "type": "string",
                    "description": "New status value (e.g. 'In Progress', 'Closed').",
                },
                "priority": {
                    "type": "string",
                    "description": "New priority: 'High', 'Medium', or 'Low'.",
                },
                "extra_fields": {
                    "type": "object",
                    "description": "Any additional Case field/value pairs to update.",
                },
            },
        },
    ),
    types.Tool(
        name="query_opportunities",
        description=(
            "Search or list Salesforce Opportunity records. "
            "Optionally filter by stage name or Account Id."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "stage": {
                    "type": "string",
                    "description": (
                        "Opportunity stage to filter on "
                        "(e.g. 'Prospecting', 'Qualification', 'Closed Won')."
                    ),
                },
                "account_id": {
                    "type": "string",
                    "description": "Salesforce Account Id to restrict opportunities to.",
                },
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "List of API field names to return. "
                        "Defaults to: Id, Name, StageName, Amount, CloseDate, "
                        "Probability, AccountId, Account.Name, OwnerId, Type, "
                        "LeadSource, CreatedDate, LastModifiedDate."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of records to return (1-200). Default 20.",
                    "minimum": 1,
                    "maximum": 200,
                    "default": 20,
                },
            },
        },
    ),
]


# ---------------------------------------------------------------------------
# MCP handlers
# ---------------------------------------------------------------------------


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return _TOOLS


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict[str, Any]
) -> list[types.TextContent]:
    """Dispatch incoming tool calls to the appropriate Salesforce method."""
    try:
        result = _dispatch(name, arguments)
        text = json.dumps(result, indent=2, default=str)
        return [types.TextContent(type="text", text=text)]

    except SalesforceAuthError as exc:
        logger.error("Authentication error: %s", exc)
        return [types.TextContent(type="text", text=f"Authentication error: {exc}")]

    except SalesforceAPIError as exc:
        logger.error("Salesforce API error: %s", exc)
        return [types.TextContent(type="text", text=f"Salesforce API error: {exc}")]

    except Exception as exc:
        logger.exception("Unexpected error in tool '%s'", name)
        return [types.TextContent(type="text", text=f"Unexpected error: {exc}")]


# ---------------------------------------------------------------------------
# Dispatch logic
# ---------------------------------------------------------------------------


def _dispatch(name: str, args: dict[str, Any]) -> Any:
    client = _get_client()

    if name == "query_accounts":
        return client.query_accounts(
            search=args.get("search"),
            fields=args.get("fields"),
            limit=int(args.get("limit", 20)),
        )

    if name == "query_contacts":
        return client.query_contacts(
            search=args.get("search"),
            account_id=args.get("account_id"),
            fields=args.get("fields"),
            limit=int(args.get("limit", 20)),
        )

    if name == "query_cases":
        return client.query_cases(
            status=args.get("status"),
            account_id=args.get("account_id"),
            fields=args.get("fields"),
            limit=int(args.get("limit", 20)),
        )

    if name == "create_case":
        data: dict[str, Any] = {
            "Subject": args["subject"],
            "Status": args.get("status", "New"),
            "Priority": args.get("priority", "Medium"),
        }
        if args.get("description"):
            data["Description"] = args["description"]
        if args.get("origin"):
            data["Origin"] = args["origin"]
        if args.get("account_id"):
            data["AccountId"] = args["account_id"]
        if args.get("contact_id"):
            data["ContactId"] = args["contact_id"]
        data.update(args.get("extra_fields") or {})
        return client.create_case(data)

    if name == "update_case":
        case_id: str = args["case_id"]
        data = {}
        for src_key, sf_key in [
            ("subject", "Subject"),
            ("description", "Description"),
            ("status", "Status"),
            ("priority", "Priority"),
        ]:
            if args.get(src_key) is not None:
                data[sf_key] = args[src_key]
        data.update(args.get("extra_fields") or {})
        return client.update_case(case_id, data)

    if name == "query_opportunities":
        return client.query_opportunities(
            stage=args.get("stage"),
            account_id=args.get("account_id"),
            fields=args.get("fields"),
            limit=int(args.get("limit", 20)),
        )

    raise ValueError(f"Unknown tool: {name!r}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def _run() -> None:
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="salesforce-mcp",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(_run())
