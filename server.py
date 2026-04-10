"""
Cognitive MCP Server — Customer Support Agent
Use Case 2: Intelligent Customer Support System

Agents:
  1. classify_issue     → Understands customer intent
  2. fetch_account_info → Retrieves relevant account data
  3. generate_response  → Drafts accurate replies
  4. escalate_case      → Flags complex issues for human review
"""

import os
import json
import random
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import JSONResponse
import uvicorn

# ─────────────────────────────────────────────
# Mock Customer Database
# ─────────────────────────────────────────────
CUSTOMERS = {
    "101": {"name": "John Smith",  "plan": "Premium",    "balance": "$120.00", "status": "Active",    "open_tickets": 1, "last_payment": "2025-03-01"},
    "102": {"name": "Sara Lee",    "plan": "Basic",      "balance": "$60.00",  "status": "Active",    "open_tickets": 0, "last_payment": "2025-03-15"},
    "103": {"name": "Mike Chen",   "plan": "Enterprise", "balance": "$540.00", "status": "Suspended", "open_tickets": 3, "last_payment": "2025-01-20"},
}

ESCALATION_LOG = []

# ─────────────────────────────────────────────
# MCP Server
# ─────────────────────────────────────────────
server = Server("cognitive-support-agent")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="classify_issue",
            description="Agent 1 — Intent Classifier. Analyzes the customer's query and returns: refund | billing | technical | account | escalate | general",
            inputSchema={
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Raw customer query text"}},
                "required": ["query"],
            },
        ),
        Tool(
            name="fetch_account_info",
            description="Agent 2 — Account Data Fetcher. Retrieves customer account details by customer ID.",
            inputSchema={
                "type": "object",
                "properties": {"customer_id": {"type": "string", "description": "Unique customer ID e.g. 101, 102, 103"}},
                "required": ["customer_id"],
            },
        ),
        Tool(
            name="generate_response",
            description="Agent 3 — Response Generator. Drafts a customer-facing reply based on issue type and account context.",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_type":      {"type": "string", "description": "Classified issue type from classify_issue"},
                    "customer_name":   {"type": "string", "description": "Customer's name for personalization"},
                    "account_details": {"type": "object", "description": "Account data from fetch_account_info"},
                },
                "required": ["issue_type", "customer_name"],
            },
        ),
        Tool(
            name="escalate_case",
            description="Agent 4 — Escalation Handler. Flags a case for human review. Returns a ticket ID and priority level.",
            inputSchema={
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "Customer ID being escalated"},
                    "reason":      {"type": "string", "description": "Why the case needs escalation"},
                    "issue_type":  {"type": "string", "description": "Classified issue type"},
                },
                "required": ["customer_id", "reason"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:

    # ── Agent 1: Classify Issue ──────────────────────────────
    if name == "classify_issue":
        q = arguments.get("query", "").lower()
        if any(w in q for w in ["refund", "money back", "reimburse", "chargeback"]):
            issue_type = "refund"
        elif any(w in q for w in ["bill", "invoice", "payment", "charge", "overcharged", "fee"]):
            issue_type = "billing"
        elif any(w in q for w in ["not working", "error", "bug", "crash", "down", "broken", "slow"]):
            issue_type = "technical"
        elif any(w in q for w in ["suspend", "cancel", "upgrade", "downgrade", "plan", "account"]):
            issue_type = "account"
        elif any(w in q for w in ["angry", "lawsuit", "legal", "fraud", "scam", "urgent", "manager"]):
            issue_type = "escalate"
        else:
            issue_type = "general"
        return [TextContent(type="text", text=json.dumps({
            "issue_type": issue_type,
            "original_query": arguments.get("query", "")
        }))]

    # ── Agent 2: Fetch Account Info ──────────────────────────
    elif name == "fetch_account_info":
        cid = arguments.get("customer_id", "").strip()
        customer = CUSTOMERS.get(cid)
        if not customer:
            return [TextContent(type="text", text=json.dumps({"error": f"Customer ID {cid} not found"}))]
        return [TextContent(type="text", text=json.dumps({"customer_id": cid, **customer}))]

    # ── Agent 3: Generate Response ───────────────────────────
    elif name == "generate_response":
        issue_type = arguments.get("issue_type", "general")
        name_val   = arguments.get("customer_name", "Customer")
        account    = arguments.get("account_details", {})
        plan       = account.get("plan", "your plan")
        balance    = account.get("balance", "N/A")
        status     = account.get("status", "Active")

        responses = {
            "refund":    f"Dear {name_val}, we've reviewed your refund request. Your {plan} plan balance is {balance}. Refunds are processed within 5–7 business days.",
            "billing":   f"Dear {name_val}, your {plan} plan shows a balance of {balance}. Share your invoice number and we'll investigate within 24 hours.",
            "technical": f"Dear {name_val}, our team is on it. As a {plan} member you have priority support — expect a response within 2 hours.",
            "account":   f"Dear {name_val}, your account is '{status}' on the {plan} plan with balance {balance}. How can we assist?",
            "general":   f"Dear {name_val}, thank you for contacting support. We'll respond within 24 hours ({plan} plan).",
        }
        return [TextContent(type="text", text=responses.get(issue_type, responses["general"]))]

    # ── Agent 4: Escalate Case ───────────────────────────────
    elif name == "escalate_case":
        cid      = arguments.get("customer_id", "unknown")
        reason   = arguments.get("reason", "Unspecified")
        issue    = arguments.get("issue_type", "general")
        customer = CUSTOMERS.get(cid, {})
        plan     = customer.get("plan", "Unknown")
        priority = "HIGH" if plan in ("Enterprise", "Premium") or customer.get("status") == "Suspended" else "MEDIUM"
        sla      = "1 hour" if priority == "HIGH" else "4 hours"
        ticket   = {
            "ticket_id":   f"ESC-{random.randint(10000, 99999)}",
            "customer_id": cid,
            "issue_type":  issue,
            "reason":      reason,
            "priority":    priority,
            "sla":         sla,
            "status":      "Open",
            "assigned_to": "Human Support Team",
            "message":     f"Escalated with {priority} priority. Agent will contact customer within {sla}.",
        }
        ESCALATION_LOG.append(ticket)
        return [TextContent(type="text", text=json.dumps(ticket))]

    return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


# ─────────────────────────────────────────────
# SSE Transport
# connect_sse is an @asynccontextmanager — MUST use async with
# ─────────────────────────────────────────────
transport = SseServerTransport("/messages")


async def handle_sse(scope, receive, send):
    async with transport.connect_sse(scope, receive, send) as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


async def handle_messages(scope, receive, send):
    await transport.handle_post_message(scope, receive, send)


# ─────────────────────────────────────────────
# REST endpoints via Starlette
# ─────────────────────────────────────────────
async def health(request: Request):
    return JSONResponse({"status": "ok", "server": "cognitive-support-agent", "tools": 4})


async def escalations(request: Request):
    return JSONResponse({"escalations": ESCALATION_LOG, "count": len(ESCALATION_LOG)})


_starlette = Starlette(routes=[
    Route("/health",      health),
    Route("/escalations", escalations),
])


# ─────────────────────────────────────────────
# Top-level ASGI dispatcher
#
# WHY NOT Mount()?
#   Starlette's Mount redirects /sse → /sse/ with a 307.
#   The MCP gateway sees that redirect and gives up (502).
#   This bare ASGI dispatcher routes BEFORE Starlette touches it.
# ─────────────────────────────────────────────
async def app(scope, receive, send):
    path = scope.get("path", "").rstrip("/")
    if path == "/sse":
        await handle_sse(scope, receive, send)
    elif path == "/messages":
        await handle_messages(scope, receive, send)
    else:
        await _starlette(scope, receive, send)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port)