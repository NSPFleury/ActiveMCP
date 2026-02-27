# ActiveMCP — Salesforce MCP Server for Healthcare

**Author:** Noelle Fleury  
**Assessment:** Salesforce MCP Server Design & Development  
**Stack:** Python · Salesforce REST API · OAuth 2.0 · Model Context Protocol

---

## A Note on How This README Was Written

This README was drafted with the assistance of Claude, but everything in it came from me. Over the course of this assessment I kept running notes, talking points, and a brain dump of my thought process as I worked through each objective. I shared those notes with Claude and asked it to help me organize and articulate them — the same way I might ask a colleague to help me clean up a document I drafted. The analogies, the decisions, the lessons learned, the scope rationale — those are mine. Claude helped me present them clearly.

The flowchart and architecture diagrams in the presentation were also generated with Claude's help based on my descriptions of how the system works.

---

## Presentation

The full walkthrough of this project — including my thought process, consulting approach, and live demo screenshots — is available here:

🔗 **[View Presentation](#)**

--- 

## What This Is

This repository contains a working Model Context Protocol (MCP) server that connects Claude to Salesforce, enabling natural language interaction with CRM data for healthcare clients and the consultants who support them.

A consultant or healthcare client staff member can ask Claude a plain-language question — *"What opportunities do we have open with device vendors?"* — and receive a real answer pulled directly from Salesforce, without ever opening the Salesforce UI.

---

## The Neighbor Analogy

Before diving into the technical details, here is the mental model that grounded this entire project.

An MCP server works like asking your neighbor for a cup of sugar. You knock on the door. They answer. You **stay on the porch** — you never enter their house. They go to their kitchen, grab the sugar, and bring it back to you. You never see their other ingredients, their fridge, or anything else in their home.

That porch is the security boundary. Claude never has direct access to Salesforce. It only receives what the MCP server is built to return — nothing more, nothing less.

The technical version of that same flow:

```
Claude receives question
  → passes it to the MCP server
  → MCP server checks for a valid OAuth access token
  → sends a SOQL query to Salesforce REST API
  → Salesforce returns matching records
  → MCP server formats the response
  → Claude delivers the answer
```

---

## Why I Built It This Way

I came into this assessment having never heard of Model Context Protocol. My first search for "MCP" returned results about non-custodial parenting. That gap closed quickly — but the way I closed it is worth documenting.

Rather than reading documentation first, I asked questions until I could explain the concept in my own words. The neighbor analogy came from that process. Once I could draw the architecture on a napkin in plain English, the implementation decisions became obvious.

I also kept asking: *"But who is actually using this?"* The assessment asked for healthcare use cases, and my first draft scoped it entirely for consultants. Catching that gap and correcting it — grounding the use cases in what healthcare client staff actually do day to day — was a reminder that the best technical work is always built around a real human on the other end of it.

---

## Who This Is For

This MCP server is designed for two user personas:

**Primary — Healthcare Client Staff**  
Physician liaisons, patient services coordinators, business development managers, and account managers at health systems, hospital networks, and med tech companies. These users interact with Salesforce daily but are not technical. They need fast answers without navigating complex UI.

*Example: A med tech sales rep who needs to confirm they're calling the right contact about the right product — not reaching out to a dentist's office about asthma medication.*

**Secondary — Consulting Firm Staff**  
Consultants supporting healthcare clients who need visibility into client Salesforce environments. Rather than submitting ad hoc data requests to a client contact, a consultant asks Claude directly.

The dual-persona scope is an intentional design choice. The same three functions serve both user types. In production, a consulting firm would deploy separate instances with different permission scopes — one client-facing, one internal — but the underlying MCP architecture is identical.

---

## Three Core Functions

### 1. Query Accounts & Contacts — *"Who are we working with?"*

Returns Salesforce Account and Contact records based on a plain-language search.

**Healthcare client:** A physician liaison pulls up a referring physician group before an outreach call — contact history, affiliated hospital, account status — without touching the Salesforce UI.

**Consultant:** Pulls the client account overview before a quarterly business review. No Salesforce login, no waiting on a data pull.

### 2. Create & Update Cases — *"What are we currently working on?"*

Creates a new Salesforce Case or updates an existing one from a natural language instruction.

**Healthcare client:** A patient services coordinator logs a provider escalation — billing dispute, high priority — by describing the situation to Claude. The Case is created with all fields populated automatically.

**Consultant:** Logs a new implementation issue mid-engagement directly through Claude rather than routing through the client's Salesforce admin.

### 3. Query Opportunities — *"What's on the horizon?"*

Returns open Opportunity records filtered by account, stage, or keyword.

**Healthcare client:** A business development manager gets a pipeline status check before a leadership meeting — stage, value, and account — in seconds.

**Consultant:** Checks where a client stands on an upcoming renewal before advising on contract strategy.

---

## Technical Decisions & Trade-offs

### REST API over SOAP or Bulk API
Salesforce offers multiple API types. REST was selected because it is the modern standard, widely documented, and appropriate for on-demand record-level queries. The SOAP API is older and more rigid — the difference between texting someone and mailing them a formal letter. The Bulk API is designed for mass operations like importing 100,000 records, which is not relevant here.

### Client Credentials OAuth Flow
This implementation uses the OAuth 2.0 Client Credentials flow via a Salesforce External Client App. This was discovered through troubleshooting — newer Salesforce Developer Edition orgs on the `develop.my.salesforce.com` infrastructure require the Client Credentials flow and the full My Domain URL rather than the standard `test.salesforce.com` endpoint. In production, the JWT Bearer Flow is the recommended standard for server-to-server integrations.

### Scoping to Three Universal Salesforce Objects
Accounts, Contacts, Cases, and Opportunities were chosen because they exist in virtually every Salesforce org regardless of edition or configuration. This makes the server maximally portable across client environments — a key consideration when a consulting firm may support multiple healthcare organizations simultaneously.

### Explicit PHI Exclusion
Keeping Protected Health Information out of scope was a risk management decision, not just a technical one. Integrating with Epic or pulling clinical data would introduce HIPAA compliance complexity requiring legal review, BAA agreements, and significantly more security architecture. Scoping to operational CRM data only keeps this implementation useful while keeping it clean.

### API Rate Limits as a Production Constraint
Salesforce Enterprise Edition orgs receive approximately 100,000 API calls per day. For a small consulting team this is not a concern. For a large health system deploying this broadly, a monitoring and throttling strategy would be essential. From a consulting perspective, this is something to flag during the design phase and build a governance strategy around — including API Usage Monitoring Dashboards with daily consumption tracking and alert thresholds.

---

## What Is Out of Scope

- Integration with Epic or any Electronic Health Record system
- Access to Protected Health Information (PHI)
- Salesforce Health Cloud-specific objects *(natural Phase 2)*
- Bulk data operations and analytics queries
- Multi-org support for consulting firms *(natural Phase 3)*
- Automated tracker updates in Jira or Excel *(future capability — currently consultants query an opportunity and then manually update trackers; this could be automated)*

---

## Setup Instructions

### Prerequisites
- Python 3.10+
- A Salesforce Developer Edition org
- A Salesforce External Client App with Client Credentials Flow enabled

### Installation

```bash
git clone https://github.com/NSPFleury/ActiveMCP.git
cd ActiveMCP
pip install -r requirements.txt
```

### Configuration

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` with your values:

```
SF_CONSUMER_KEY=your_consumer_key
SF_CONSUMER_SECRET=your_consumer_secret
SF_MY_DOMAIN=yourorg.develop.my.salesforce.com
SF_API_VERSION=v59.0
```

> ⚠️ The `.env` file is git-ignored and will never be committed to the repository. Never share your Consumer Key, Consumer Secret, or Security Token publicly.

### Salesforce Setup Requirements

1. Create an External Client App in Salesforce Setup → External Client App Manager
2. Enable OAuth with `Full access (full)` scope
3. Under Policies → Enable Client Credentials Flow
4. Set a Run As user (your Salesforce username)
5. Copy the Consumer Key and Consumer Secret into your `.env`

### Running the Test Script

```bash
python test_functions.py
```

A successful run will authenticate and return live Account, Contact, and Opportunity records from your Salesforce org.

### Running the MCP Server

```bash
python -m src.server
```

---

## Project Structure

```
ActiveMCP/
├── src/
│   ├── auth.py          # OAuth 2.0 authentication module
│   ├── salesforce.py    # Salesforce REST API client
│   └── server.py        # MCP server with 6 registered tools
├── test_functions.py    # Standalone test script
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variable template
└── README.md            # This file
```

---

## MCP Tools Registered

| Tool | Description |
|------|-------------|
| `query_accounts` | Filter accounts by name, custom fields, limit |
| `query_contacts` | Filter contacts by name, email, or Account ID |
| `query_cases` | Filter cases by status or Account ID |
| `create_case` | Create a new Case with subject, priority, origin |
| `update_case` | Patch any fields on an existing Case by ID |
| `query_opportunities` | Filter opportunities by stage or Account ID |

---

## Lessons Learned

**On learning unfamiliar technology:**  
The most useful thing I did early on was not read documentation. It was ask questions until I could explain the concept in my own words. That is a habit from consulting — you cannot advise a client on something you cannot explain simply.

**On scope definition:**  
My first draft of this project scoped the MCP server entirely for consultants. The assessment asked for healthcare client use cases. Catching that gap and correcting it was a reminder that the best technical work is always built around a real human on the other end of it.

**On troubleshooting:**  
This implementation encountered multiple authentication challenges — wrong grant type, wrong domain format, missing OAuth scopes, trailing slash URL bugs. Each error was informative. Documenting what failed and why is as valuable as documenting what worked. A consultant who can articulate what went wrong and how they resolved it is more valuable than one who only shows a clean demo.

**On credential security:**  
During this assessment, credentials were accidentally exposed in a screenshot. They were rotated immediately. This is a real-world lesson: `.gitignore` your `.env`, never paste credentials into chat, and treat a security incident as an opportunity to demonstrate incident response — not as a failure.

---

## Future Roadmap

- Salesforce Health Cloud object support
- Epic EHR integration *(requires HIPAA compliance architecture)*
- JWT Bearer Flow for production authentication
- Multi-org support for consulting firm deployments
- Automated Jira and tracker updates post-query
- API usage monitoring and rate limit governance

---

*Built as a technical assessment for an Agentic AI consulting firm. Starting point: not knowing what MCP stood for. Ending point: a working Salesforce MCP server with live data retrieval. Time elapsed: approximately 48 hours.*

---

## The Real Project Metrics

Because no technical assessment is complete without the full picture:

| Metric | Value |
|--------|-------|
| Stress Diet Cokes consumed | 9 |
| Times I Googled "NCP" before realizing you said "MCP" | Too many |
| OAuth errors encountered | 7 |
| OAuth errors resolved | 7 |
| Analogies involving neighbors and sugar | 1 (it did a lot of work) |
| Credentials accidentally exposed in a screenshot | 1 (rotated immediately, lesson learned) |
| Hours of train ride productivity | ~4 |
| Times I said "I think I broke it" | Several |
| Times it was actually broken | Also several |
| Working Salesforce functions delivered | 6 |
