"""
Quick smoke test for query_accounts, query_contacts, and query_opportunities.
Run from the project root: python test_functions.py
"""

import json
from dotenv import load_dotenv
from src.auth import SalesforceAuth, SalesforceAuthError
from src.salesforce import SalesforceClient, SalesforceAPIError

load_dotenv()


def print_results(label: str, records: list) -> None:
    print(f"\n{'='*60}")
    print(f"{label}  ({len(records)} record(s))")
    print("=" * 60)
    for rec in records:
        print(json.dumps(rec, indent=2, default=str))


def main() -> None:
    print("Authenticating with Salesforce...")
    auth = SalesforceAuth()
    token = auth.get_token()
    print(f"  instance : {token.instance_url}")
    print(f"  api ver  : {auth.api_version}")

    client = SalesforceClient(auth)
    print(f"  base url : {auth.rest_base_url()}")
    print(f"  query url: {auth.rest_base_url()}/query")

    # --- Accounts ---
    accounts = client.query_accounts(limit=5)
    print_results("ACCOUNTS", accounts)

    # --- Contacts ---
    contacts = client.query_contacts(limit=5)
    print_results("CONTACTS", contacts)

    # --- Opportunities ---
    opportunities = client.query_opportunities(limit=5)
    print_results("OPPORTUNITIES", opportunities)

    print("\nDone.")


if __name__ == "__main__":
    try:
        main()
    except SalesforceAuthError as exc:
        print(f"\n[Auth error] {exc}")
    except SalesforceAPIError as exc:
        print(f"\n[API error]  {exc}")
