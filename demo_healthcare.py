"""
demo_healthcare.py — Salesforce MCP Healthcare Demo

Demonstrates three MCP capabilities in a healthcare context:
  1. Account & Contact lookup  — pre-meeting client brief
  2. Case creation             — provider billing dispute
  3. Opportunity pipeline      — open deals report

Run from the project root:
    python demo_healthcare.py
"""

from __future__ import annotations

from typing import Optional
from dotenv import load_dotenv
from src.auth import SalesforceAuth, SalesforceAuthError
from src.salesforce import SalesforceClient, SalesforceAPIError

load_dotenv()

BAR  = "─" * 62
DBAR = "═" * 62


def header(title: str) -> None:
    print(f"\n{DBAR}")
    print(f"  {title}")
    print(DBAR)


def row(label: str, value, width: int = 20) -> None:
    display = value if value not in (None, "", "null", {}) else "—"
    print(f"  {label:<{width}} {display}")


# ---------------------------------------------------------------------------
# 1. Account & Contact Lookup
# ---------------------------------------------------------------------------

def demo_client_brief(client: SalesforceClient) -> Optional[str]:
    """
    Pull up any available account and its contacts,
    presented like a consultant's pre-meeting brief.
    """
    header("CAPABILITY 1  —  Account & Contact Lookup")

    print("""
  Imagine you're a patient services rep about to jump on a call.
  Let's pull up the client record so you're not walking in blind.
""")

    print("  Searching Salesforce for an account...")
    accounts = client.query_accounts(limit=1)

    if not accounts:
        print("  No accounts found in the org.")
        return None

    acct     = accounts[0]
    acct_id  = acct.get("Id", "")
    name     = acct.get("Name", "Unknown")

    print(f"  Found: {name}\n")
    print(f"  {BAR}")
    print(f"  CLIENT OVERVIEW")
    print(f"  {BAR}")
    row("Account:",  name)
    row("Industry:", acct.get("Industry"))
    row("Type:",     acct.get("Type"))
    row("Phone:",    acct.get("Phone"))
    row("Website:",  acct.get("Website"))
    row("Location:", ", ".join(filter(None, [
        acct.get("BillingCity"),
        acct.get("BillingState"),
        acct.get("BillingCountry"),
    ])) or None)

    print(f"\n  Now pulling up the key contacts at {name}...\n")
    contacts = client.query_contacts(account_id=acct_id, limit=5)

    if contacts:
        print(f"  {BAR}")
        print(f"  KEY CONTACTS  ({len(contacts)} on file)")
        print(f"  {BAR}")
        for c in contacts:
            full_name = f"{c.get('FirstName', '')} {c.get('LastName', '')}".strip()
            print(f"\n  {full_name}")
            print(f"    Title  : {c.get('Title') or '—'}")
            print(f"    Email  : {c.get('Email') or '—'}")
            print(f"    Phone  : {c.get('Phone') or '—'}")
        print()
    else:
        print(f"  No contacts on file for {name} yet.\n")

    print(f"  You're all set — account brief loaded for {name}.")
    return acct_id


# ---------------------------------------------------------------------------
# 2. Case Creation
# ---------------------------------------------------------------------------

def demo_create_case(client: SalesforceClient, account_id: Optional[str]) -> None:
    """
    Open a new Provider Billing Dispute case and confirm it was created.
    """
    header("CAPABILITY 2  —  Case Creation")

    print("""
  A billing inquiry just came in from Dr. Patel at Northwestern.
  Let's log a case so it's tracked, assigned, and doesn't fall
  through the cracks.
""")

    payload: dict = {
        "Subject":     "Provider Billing Dispute",
        "Priority":    "High",
        "Description": "Follow up required on billing inquiry from Dr. Patel at Northwestern",
        "Status":      "New",
    }
    if account_id:
        payload["AccountId"] = account_id

    print("  Creating case in Salesforce...")
    result = client.create_case(payload)

    if not result.get("success"):
        errors = result.get("errors", [])
        print(f"\n  Case creation failed: {errors}")
        return

    case_id = result["id"]
    print(f"\n  Case created successfully.\n")
    print(f"  {BAR}")
    print(f"  NEW CASE SUMMARY")
    print(f"  {BAR}")
    row("Subject:",     payload["Subject"])
    row("Priority:",    payload["Priority"])
    row("Status:",      payload["Status"])
    row("Description:", payload["Description"])
    row("Salesforce ID:", case_id)

    # Query it back to confirm it's live
    print(f"\n  Double-checking that the case is visible in Salesforce...")
    soql = (
        f"SELECT Id, CaseNumber, Subject, Priority, Status, CreatedDate "
        f"FROM Case WHERE Id = '{case_id}'"
    )
    confirmed = client._query(soql)

    if confirmed:
        c = confirmed[0]
        print(f"\n  Confirmed — Case #{c.get('CaseNumber')} is live.")
        print(f"  Opened: {c.get('CreatedDate', '—')}")
        print(f"\n  Dr. Patel's billing issue is now on the radar.")
    else:
        print("  Could not confirm the case record — check Salesforce directly.")


# ---------------------------------------------------------------------------
# 3. Opportunity Pipeline
# ---------------------------------------------------------------------------

def demo_pipeline(client: SalesforceClient) -> None:
    """
    Pull all opportunities and display them as a pipeline report,
    filtering to open stages only.
    """
    header("CAPABILITY 3  —  Open Opportunity Pipeline")

    print("""
  Let's pull up the pipeline — every open deal currently in
  Salesforce, sorted by value. Think of this as your weekly
  business development snapshot.
""")

    print("  Fetching opportunities from Salesforce...")
    opps = client.query_opportunities(limit=50)

    closed_stages = {"Closed Won", "Closed Lost"}
    open_opps = [o for o in opps if o.get("StageName") not in closed_stages]
    open_opps.sort(key=lambda o: o.get("Amount") or 0, reverse=True)

    if not open_opps:
        print("  No open opportunities in the pipeline right now.")
        return

    total = sum(o.get("Amount") or 0 for o in open_opps)
    count = len(open_opps)
    noun  = "opportunity" if count == 1 else "opportunities"

    print(f"\n  {BAR}")
    print(f"  PIPELINE SNAPSHOT  —  {count} open {noun}")
    print(f"  {BAR}\n")

    for i, opp in enumerate(open_opps, 1):
        name    = opp.get("Name", "Unnamed")
        stage   = opp.get("StageName", "—")
        amount  = opp.get("Amount")
        close   = opp.get("CloseDate", "—")
        account = (opp.get("Account") or {}).get("Name") or "—"
        prob    = opp.get("Probability")

        amount_str = f"${amount:,.0f}" if amount is not None else "—"
        prob_str   = f"{int(prob)}% probability" if prob is not None else ""

        print(f"  {i:>2}.  {name}")
        print(f"       Account    : {account}")
        print(f"       Stage      : {stage}  {prob_str}")
        print(f"       Value      : {amount_str}")
        print(f"       Close Date : {close}")
        print()

    print(f"  {BAR}")
    print(f"  Total open pipeline value:  ${total:,.0f}")
    print(f"\n  That's your pipeline. {count} deal{'s' if count != 1 else ''} to focus on.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"\n{DBAR}")
    print("  SALESFORCE MCP  —  HEALTHCARE DEMO")
    print("  Account lookup  |  Case creation  |  Pipeline report")
    print(DBAR)

    print("\n  Connecting to Salesforce...")
    auth   = SalesforceAuth()
    client = SalesforceClient(auth)
    print(f"  Connected to {auth.instance_url}\n")

    account_id = demo_client_brief(client)
    demo_create_case(client, account_id)
    demo_pipeline(client)

    header("DEMO COMPLETE")
    print("""
  All three MCP capabilities exercised successfully:

    1. Account & Contact Lookup  — client brief pulled before a meeting
    2. Case Creation             — billing dispute logged and confirmed
    3. Opportunity Pipeline      — open deals surfaced for review

  This is how Claude can support patient services, provider relations,
  and business development teams — using plain language to drive
  real actions in Salesforce.
""")


if __name__ == "__main__":
    try:
        main()
    except SalesforceAuthError as exc:
        print(f"\n  [Auth error]  {exc}\n")
    except SalesforceAPIError as exc:
        print(f"\n  [API error]   {exc}\n")
