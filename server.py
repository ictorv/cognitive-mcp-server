from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool
from starlette.applications import Starlette
from starlette.routing import Route
import uvicorn
import os

# Create MCP server
server = Server("cognitive-support-agent")

# Example customer database
CUSTOMERS = {
    "101": {"name": "John", "plan": "Premium", "balance": "$120"},
    "102": {"name": "Sara", "plan": "Basic", "balance": "$60"},
}

# Define MCP tools
tools = [
    Tool(
        name="classify_issue",
        description="Classify customer query into category",
        inputSchema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"]
        },
    ),
    Tool(
        name="get_account_info",
        description="Fetch customer account information",
        inputSchema={
            "type": "object",
            "properties": {"customer_id": {"type": "string"}},
            "required": ["customer_id"]
        },
    ),
    Tool(
        name="generate_response",
        description="Generate support response",
        inputSchema={
            "type": "object",
            "properties": {
                "issue_type": {"type": "string"},
                "customer_name": {"type": "string"}
            },
            "required": ["issue_type", "customer_name"]
        },
    ),
    Tool(
        name="escalate_case",
        description="Escalate complex issues",
        inputSchema={
            "type": "object",
            "properties": {"issue_type": {"type": "string"}},
            "required": ["issue_type"]
        },
    ),
]

# Return tool list
@server.list_tools()
async def list_tools():
    return tools


# Tool execution
@server.call_tool()
async def call_tool(name, arguments):

    if name == "classify_issue":
        query = arguments["query"].lower()

        if "bill" in query or "payment" in query:
            return {"issue_type": "billing"}

        if "refund" in query:
            return {"issue_type": "refund"}

        if "order" in query or "delivery" in query:
            return {"issue_type": "order_status"}

        return {"issue_type": "general_support"}


    if name == "get_account_info":
        cid = arguments["customer_id"]
        return CUSTOMERS.get(cid, {"error": "Customer not found"})


    if name == "generate_response":
        issue = arguments["issue_type"]
        customer = arguments["customer_name"]

        if issue == "billing":
            return {"response": f"Hello {customer}, we are reviewing your billing details."}

        if issue == "refund":
            return {"response": f"Hello {customer}, your refund request is being processed."}

        if issue == "order_status":
            return {"response": f"Hello {customer}, your order is currently on the way."}

        return {"response": f"Hello {customer}, our support team will assist you shortly."}


    if name == "escalate_case":
        issue = arguments["issue_type"]

        if issue in ["refund", "billing"]:
            return {"escalation": "Escalated to human support agent"}

        return {"escalation": "No escalation required"}


# SSE transport setup
transport = SseServerTransport("/messages")


# SSE connection endpoint
async def handle_sse(request):
    return await transport.handle_sse(request, server)


# Endpoint for tool calls
async def handle_messages(request):
    return await transport.handle_post(request)


# Web application
app = Starlette(
    routes=[
        Route("/sse", handle_sse),
        Route("/messages", handle_messages, methods=["POST"]),
    ]
)


# Run server (Render compatible)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)