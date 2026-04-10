# 🤖 Cognitive MCP Server: Intelligent Customer Support Agent

> A multi-agent AI system that automatically classifies customer queries, fetches account data, drafts personalized replies, and escalates complex cases - built with the **Model Context Protocol (MCP)**, deployed on **Render**, and orchestrated via **IBM Consulting Advantage Agent Studio**.

---

## 📌 What This Project Does

Instead of a human agent manually triaging support tickets, this system uses **4 AI agents working in sequence** to handle customer queries end-to-end:

```
Customer Query
      ↓
  Agent 1: Classify Intent       → billing / refund / technical / account / escalate
      ↓
  Agent 2: Fetch Account Info    → name, plan, balance, status
      ↓
  Agent 3: Draft Response        → personalized reply based on issue + account
      ↓  (if urgent/complex)
  Agent 4: Escalate Case         → ticket ID, HIGH/MEDIUM priority, SLA assigned
      ↓
  Final Response to Customer
```

---

## 🗂️ Project Structure

```
cognitive-mcp-server/
├── server.py            # MCP server with all 4 agent tools
├── requirements.txt     # Python dependencies
└── render.yaml          # Render deployment config
```

---

## 🛠️ Tech Stack

| Layer | Technology | Why Used |
|---|---|---|
| Protocol | Model Context Protocol (MCP) | Exposes tools to AI agents |
| Transport | SSE (Server-Sent Events) | Real-time streaming between agent and server |
| Server | Python + Starlette + Uvicorn | Lightweight ASGI web server |
| MCP Library | `mcp` (Python) | Tool registration + SSE transport |
| Deployment | Render.com | Free cloud hosting |
| Agent Platform | IBM Consulting Advantage (ICA) | Multi-agent orchestration UI |
| Orchestration | Autogen (Supervisor pattern) | Supervisor directs 4 worker agents |
| LLM | GPT-4o / GPT-5-blueprint (ICA) | Agent reasoning |

---

## 🤖 The 4 Agents - How Each Is Implemented

### Agent 1 - `classify_issue` (Intent Classifier)

**What it does:** Reads the customer's raw query and figures out what type of problem it is.

**How it works:** Simple keyword matching against the query string.

```python
if any(w in query for w in ["refund", "money back", "reimburse"]):
    issue_type = "refund"
elif any(w in query for w in ["bill", "invoice", "overcharged"]):
    issue_type = "billing"
elif any(w in query for w in ["not working", "error", "crash"]):
    issue_type = "technical"
elif any(w in query for w in ["suspend", "cancel", "upgrade", "plan"]):
    issue_type = "account"
elif any(w in query for w in ["angry", "lawsuit", "fraud", "urgent", "manager"]):
    issue_type = "escalate"
else:
    issue_type = "general"
```

**Returns:** `{ "issue_type": "billing", "original_query": "..." }`

---

### Agent 2 - `fetch_account_info` (Account Fetcher)

**What it does:** Looks up the customer's account details by their ID.

**How it works:** Looks up a Python dictionary (mock database) using the customer ID.

```python
CUSTOMERS = {
    "101": {"name": "John Smith",  "plan": "Premium",    "balance": "$120.00", "status": "Active"},
    "102": {"name": "Sara Lee",    "plan": "Basic",      "balance": "$60.00",  "status": "Active"},
    "103": {"name": "Mike Chen",   "plan": "Enterprise", "balance": "$540.00", "status": "Suspended"},
}
```

**Returns:** Full account object, or an error if the ID doesn't exist.

---

### Agent 3 - `generate_response` (Response Drafter)

**What it does:** Writes a personalized reply to the customer based on their issue type and account data.

**How it works:** Uses pre-written response templates, injecting the customer's name, plan, balance, and status dynamically.

| Issue Type | What the Response Says |
|---|---|
| `refund` | Confirms refund timeline (5–7 business days) |
| `billing` | Asks for invoice number, commits to 24hr review |
| `technical` | Acknowledges issue, promises 2hr response |
| `account` | Summarizes current account status |
| `general` | Generic acknowledgment with 24hr SLA |

**Returns:** A ready-to-send customer reply string.

---

### Agent 4 - `escalate_case` (Escalation Handler)

**What it does:** Creates a support ticket for human review when the case is too complex for auto-resolution.

**How it works:** Checks the customer's plan and account status to assign priority and SLA.

```python
if plan in ("Enterprise", "Premium") or status == "Suspended":
    priority = "HIGH"
    sla = "1 hour"
else:
    priority = "MEDIUM"
    sla = "4 hours"
```

**Returns:**
```json
{
  "ticket_id": "ESC-76532",
  "priority": "HIGH",
  "sla": "1 hour",
  "status": "Open",
  "assigned_to": "Human Support Team"
}
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│             IBM Agent Studio (ICA)              │
│                                                 │
│         CustomerSupportSupervisor               │
│    (routes tasks to the right sub-agent)        │
│                                                 │
│  ClassifierAgent  AccountFetcherAgent           │
│  ResponseGeneratorAgent  EscalationAgent        │
└────────────────────┬────────────────────────────┘
                     │ SSE (real-time)
                     ▼
┌─────────────────────────────────────────────────┐
│         MCP Server (Render.com)                 │
│  https://cognitive-mcp-server.onrender.com      │
│                                                 │
│  Tools: classify_issue, fetch_account_info,     │
│         generate_response, escalate_case        │
└─────────────────────────────────────────────────┘
```

---

## 🚀 How the Server Is Implemented (`server.py`)

The server uses a **custom ASGI dispatcher** as the entry point - this was a critical design decision (see Issues section below for why).

```python
# The entry point - routes requests BEFORE Starlette touches them
async def app(scope, receive, send):
    path = scope.get("path", "").rstrip("/")
    if path == "/sse":
        await handle_sse(scope, receive, send)      # MCP stream
    elif path == "/messages":
        await handle_messages(scope, receive, send)  # MCP messages
    else:
        await _starlette(scope, receive, send)       # health/escalations REST endpoints
```

The SSE connection is handled using `async with` (not `await`) because `connect_sse` is an async context manager:

```python
async def handle_sse(scope, receive, send):
    async with transport.connect_sse(scope, receive, send) as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
```

---

## 📦 Installation & Local Run

**1. Clone the repo**
```bash
git clone <your-repo-url>
cd cognitive-mcp-server
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

`requirements.txt`:
```
mcp
starlette
uvicorn
anyio
```

**3. Run locally**
```bash
python server.py
# Server starts at http://localhost:8000
```

**4. Verify it works**
```bash
curl http://localhost:8000/health
# → {"status":"ok","server":"cognitive-support-agent","tools":4}

curl -N http://localhost:8000/sse
# → event: endpoint
#   data: /messages?session_id=<uuid>
```

---

## ☁️ Deployment on Render

**`render.yaml`:**
```yaml
services:
  - type: web
    name: cognitive-mcp-server
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn server:app --host 0.0.0.0 --port $PORT
```

**Steps:**
1. Push code to GitHub
2. Go to [render.com](https://render.com) → **New → Web Service**
3. Connect your GitHub repo
4. Render auto-detects `render.yaml` and deploys
5. Wait for: `Application startup complete.`

**Live Endpoints:**

| Endpoint | Method | Description |
|---|---|---|
| `/sse` | GET | MCP SSE connection (used by agents) |
| `/messages` | POST | MCP message handler |
| `/health` | GET | Health check |
| `/escalations` | GET | View all escalation tickets |

---

## 🔗 IBM Agent Studio Integration

| Setting | Value |
|---|---|
| Platform | IBM Consulting Advantage (ICA) |
| Framework | Autogen |
| Orchestration Pattern | Supervisor |
| MCP Server URL | `https://cognitive-mcp-server.onrender.com/sse` |
| Transport | SSE |
| Authentication | None |

Each sub-agent in ICA is assigned exactly one MCP tool:
- `ClassifierAgent` → `classify_issue`
- `AccountFetcherAgent` → `fetch_account_info`
- `ResponseGeneratorAgent` → `generate_response`
- `EscalationAgent` → `escalate_case`

---

## ✅ End-to-End Test Result

**Test Input:**
```
My name is John, customer ID 101.
I was overcharged on my last bill and I want a refund immediately. This is urgent!
```

**Agent Execution:**

| Step | Agent | Output |
|---|---|---|
| 1 | ClassifierAgent | `issue_type: billing`, `escalate_flag: true` |
| 2 | AccountFetcherAgent | John Smith, Premium plan, $120.00, Active |
| 3 | ResponseGeneratorAgent | Personalized reply with refund timeline |
| 4 | EscalationAgent | `ESC-76532`, HIGH priority, 1 hour SLA |

All 4 agents executed in sequence. ✅

---

## 🐛 Issues Faced & How I Fixed Them

### Issue 1 - `TypeError: sse() missing 2 required positional arguments`

**Cause:** I registered the SSE handler via Starlette's `Route()`. Starlette wraps handlers to receive a single `Request` object, but MCP's SSE transport needs raw ASGI `(scope, receive, send)`.

**Fix:** Replaced `Route("/sse", handle_sse)` with a top-level `async def app(scope, receive, send)` that routes `/sse` directly, before Starlette can intercept it.

---

### Issue 2 - `TypeError: object _AsyncGeneratorContextManager can't be used in 'await' expression`

**Cause:** I wrote `await transport.connect_sse(...)`. But `connect_sse` is an `@asynccontextmanager` - it can't be awaited directly.

**Fix:** Changed to `async with`:
```python
# ❌ Wrong
await transport.connect_sse(scope, receive, send)

# ✅ Correct
async with transport.connect_sse(scope, receive, send) as (read_stream, write_stream):
    await server.run(...)
```

---

### Issue 3 - HTTP 307 Redirect on `/sse` → 502 in MCP Gateway

**Cause:** Starlette's `Mount()` has `redirect_slashes=True` by default. When the MCP gateway hit `/sse`, Starlette redirected it to `/sse/` with a 307. The gateway doesn't follow redirects, so it returned 502.

**Fix:** Two-part solution:
1. Used the top-level ASGI dispatcher (routes `/sse` before Starlette runs)
2. Set `_starlette.router.redirect_slashes = False` on the Starlette sub-app

---

### Issue 4 - HTTP 502 When Registering in MCP Gateway

**Cause:** Render's free tier puts servers to sleep after 15 minutes of inactivity. Cold start takes 30–60 seconds - long enough for the gateway to time out.

**Fix:**
1. Wake the server first: open `https://cognitive-mcp-server.onrender.com/health` in the browser
2. Confirm SSE is streaming: `curl -N https://cognitive-mcp-server.onrender.com/sse`
3. Only then register the URL in the MCP gateway (without trailing slash)

---

## 💡 Key Learnings

**On MCP & SSE:**
- `connect_sse()` is an `@asynccontextmanager` - always `async with`, never `await`
- Starlette's `Route()` and `Mount()` are not safe for raw ASGI handlers
- A plain `async def app(scope, receive, send)` is the most reliable ASGI dispatcher pattern

**On Deployment:**
- Always wake a Render free-tier server before registering with any MCP gateway
- Never use trailing slashes in MCP server URLs
- Always verify `/sse` responds with `event: endpoint` before connecting agents

**On Multi-Agent Design:**
- Supervisor pattern works best for sequential, role-based pipelines
- One agent = one tool = one responsibility (makes debugging easy)
- Priority/SLA logic belongs in the MCP tool, not the agent prompt
- Keyword-based classification is fast and predictable for MVP use cases

---

## 📍 Live URLs

| Resource | URL |
|---|---|
| MCP Server (SSE) | `https://cognitive-mcp-server.onrender.com/sse` |
| Health Check | `https://cognitive-mcp-server.onrender.com/health` |
| Escalation Log | `https://cognitive-mcp-server.onrender.com/escalations` |

---