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
import anyio
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.requests import Request
from starlette.responses import JSONResponse
import uvicorn

# ─────────────────────────────────────────────
# Mock Customer Database
# ─────────────────────────────────────────────
CUSTOMERS = {
    "101": {
        "name": "John Smith",
        "plan": "Premium",
        "balance": "$120.00",
        "status": "Active",
        "open_tickets": 1,
        "last_payment": "2025-03-01",
    },
    "102": {
        "name": "Sara Lee",
        "plan": "Basic",
        "balance": "$60.00",
        "status": "Active",
        "open_tickets": 0,
        "last_payment": "2025-03-15",
    },
    "103": {
        "name": "Mike Chen",
        "plan": "Enterprise",
        "balance": "$540.00",
        "status": "Suspended",
        "open_tickets": 3,
        "last_payment": "2025-01-20",
    },
}

ESCALATION_LOG = []

# ─────────────────────────────────────────────
# MCP Server Setup
# ─────────────────────────────────────────────
server = Server("cognitive-support-agent")

# ─────────────────────────────────────────────
# Tool Definitions
# ─────────────────────────────────────────────
@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="classify_issue",
            description=(
                "Agent 1 — Intent Classifier. "
                "Analyzes the customer's query and returns one of: "
                "refund | billing | technical | account | general | escalate"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Raw customer query text",
                    }
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="fetch_account_info",
            description=(
                "Agent 2 — Account Data Fetcher. "
                "Retrieves customer account details by customer ID."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "Unique customer identifier (e.g. 101, 102)",
                    }
                },
                "required": ["customer_id"],
            },
        ),
        Tool(
            name="generate_response",
            description=(
                "Agent 3 — Response Generator. "
                "Drafts a customer-facing reply based on issue type and account context."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_type": {
                        "type": "string",
                        "description": "Classified issue type from classify_issue",
                    },
                    "customer_name": {
                        "type": "string",
                        "description": "Customer's name for personalization",
                    },
                    "account_details": {
                        "type": "object",
                        "description": "Account data from fetch_account_info",
                    },
                },
                "required": ["issue_type", "customer_name"],
            },
        ),
        Tool(
            name="escalate_case",
            description=(
                "Agent 4 — Escalation Handler. "
                "Flags a case for human review when it's too complex to resolve automatically. "
                "Returns a ticket ID and priority level."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "Customer ID being escalated",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Why the case needs escalation",
                    },
                    "issue_type": {
                        "type": "string",
                        "description": "Classified issue type",
                    },
                },
                "required": ["customer_id", "reason"],
            },
        ),
    ]


# ─────────────────────────────────────────────
# Tool Implementations
# ─────────────────────────────────────────────
@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:

    # ── Agent 1: Classify Issue ──────────────────
    if name == "classify_issue":
        query = arguments.get("query", "").lower()

        if any(w in query for w in ["refund", "money back", "reimburse", "charge back"]):
            issue_type = "refund"
        elif any(w in query for w in ["bill", "invoice", "payment", "charge", "overcharged", "fee"]):
            issue_type = "billing"
        elif any(w in query for w in ["not working", "error", "bug", "crash", "down", "broken", "slow"]):
            issue_type = "technical"
        elif any(w in query for w in ["suspend", "cancel", "upgrade", "downgrade", "plan", "account"]):
            issue_type = "account"
        elif any(w in query for w in ["angry", "lawsuit", "legal", "fraud", "scam", "urgent", "manager"]):
            issue_type = "escalate"
        else:
            issue_type = "general"

        return [TextContent(
            type="text",
            text=f'{{"issue_type": "{issue_type}", "original_query": "{arguments.get("query", "")}"}}',
        )]

    # ── Agent 2: Fetch Account Info ──────────────
    elif name == "fetch_account_info":
        cid = arguments.get("customer_id", "").strip()
        customer = CUSTOMERS.get(cid)

        if not customer:
            return [TextContent(
                type="text",
                text=f'{{"error": "Customer ID {cid} not found", "customer_id": "{cid}"}}',
            )]

        import json
        data = {"customer_id": cid, **customer}
        return [TextContent(type="text", text=json.dumps(data))]

    # ── Agent 3: Generate Response ───────────────
    elif name == "generate_response":
        issue_type = arguments.get("issue_type", "general")
        name_val = arguments.get("customer_name", "Customer")
        account = arguments.get("account_details", {})
        plan = account.get("plan", "your plan")
        balance = account.get("balance", "N/A")
        status = account.get("status", "Active")

        responses = {
            "refund": (
                f"Dear {name_val}, we've reviewed your refund request. "
                f"Your current balance is {balance} under the {plan} plan. "
                f"Our team will process your refund within 5–7 business days. "
                f"You'll receive a confirmation email shortly."
            ),
            "billing": (
                f"Dear {name_val}, thank you for reaching out about your billing. "
                f"Your account ({plan} plan) shows a balance of {balance}. "
                f"If you believe there's an error, please share your invoice number "
                f"and we'll investigate within 24 hours."
            ),
            "technical": (
                f"Dear {name_val}, we're sorry you're experiencing a technical issue. "
                f"Our engineering team has been notified. "
                f"As a {plan} plan member, you have priority support — "
                f"expect a response within 2 hours."
            ),
            "account": (
                f"Dear {name_val}, your account status is currently '{status}' "
                f"on the {plan} plan with a balance of {balance}. "
                f"Would you like to make any changes to your plan or account settings?"
            ),
            "general": (
                f"Dear {name_val}, thank you for contacting support. "
                f"We've received your query and will get back to you within 24 hours. "
                f"Your account is on the {plan} plan."
            ),
        }

        response_text = responses.get(issue_type, responses["general"])
        return [TextContent(type="text", text=response_text)]

    # ── Agent 4: Escalate Case ───────────────────
    elif name == "escalate_case":
        import random, json
        cid = arguments.get("customer_id", "unknown")
        reason = arguments.get("reason", "Unspecified")
        issue_type = arguments.get("issue_type", "general")

        customer = CUSTOMERS.get(cid, {})
        plan = customer.get("plan", "Unknown")

        # Priority: Enterprise/Premium or suspended = HIGH
        priority = "HIGH" if plan in ("Enterprise", "Premium") or customer.get("status") == "Suspended" else "MEDIUM"
        ticket_id = f"ESC-{random.randint(10000, 99999)}"

        ticket = {
            "ticket_id": ticket_id,
            "customer_id": cid,
            "issue_type": issue_type,
            "reason": reason,
            "priority": priority,
            "assigned_to": "Human Support Team",
            "status": "Open",
            "message": f"Case {ticket_id} has been escalated with {priority} priority. A human agent will contact the customer within {'1 hour' if priority == 'HIGH' else '4 hours'}.",
        }

        ESCALATION_LOG.append(ticket)
        return [TextContent(type="text", text=json.dumps(ticket))]

    else:
        return [TextContent(type="text", text=f'{{"error": "Unknown tool: {name}"}}')]


# ─────────────────────────────────────────────
# SSE Transport — correct async context manager usage
# ─────────────────────────────────────────────
transport = SseServerTransport("/messages")


async def handle_sse(scope, receive, send):
    """
    connect_sse is an @asynccontextmanager — must be used with 'async with'.
    It yields (read_stream, write_stream) which we pass into server.run().
    """
    async with transport.connect_sse(scope, receive, send) as (read_stream, write_stream):
        init_options = server.create_initialization_options()
        await server.run(read_stream, write_stream, init_options)


async def handle_messages(scope, receive, send):
    await transport.handle_post_message(scope, receive, send)


# ─────────────────────────────────────────────
# Health check + escalation log endpoints
# ─────────────────────────────────────────────
async def health(request: Request):
    return JSONResponse({"status": "ok", "server": "cognitive-support-agent"})


async def escalations(request: Request):
    return JSONResponse({"escalations": ESCALATION_LOG, "count": len(ESCALATION_LOG)})


# ─────────────────────────────────────────────
# Starlette App — Mount for raw ASGI, Route for request handlers
# ─────────────────────────────────────────────
app = Starlette(
    routes=[
        Mount("/sse", app=handle_sse),
        Mount("/messages", app=handle_messages),
        Route("/health", health),
        Route("/escalations", escalations),
    ]
)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)