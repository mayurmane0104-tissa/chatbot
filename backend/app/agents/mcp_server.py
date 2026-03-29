"""
app/agents/mcp_server.py
FastMCP server exposing tools that the Bedrock Agent can call.
Each tool is a well-typed async function that returns structured JSON.
"""
import asyncio
import json
from datetime import datetime
from typing import Any

import structlog
from fastmcp import FastMCP

from app.core.config import settings

log = structlog.get_logger()

mcp = FastMCP(
    name=settings.MCP_SERVER_NAME,
    description="TissaTech AI Agent tool server",
)


# ── Tool: Company Information ──────────────────────────────────────────────────

@mcp.tool()
async def get_company_info(topic: str) -> dict[str, Any]:
    """
    Retrieve factual information about TissaTech company, products, and services.

    Args:
        topic: The topic to look up (e.g., "pricing", "contact", "services")

    Returns:
        Structured company information
    """
    # In production: query your DB or internal API
    COMPANY_DATA = {
        "contact": {
            "email": "hello@tissatech.com",
            "website": "https://tissatech.com",
            "support": "support@tissatech.com",
        },
        "services": [
            "Custom software development",
            "AI & ML integration",
            "Cloud architecture",
            "Digital transformation",
        ],
        "about": "TissaTech is a technology company specializing in enterprise software solutions.",
    }

    topic_lower = topic.lower()
    for key, value in COMPANY_DATA.items():
        if key in topic_lower:
            return {"topic": key, "data": value}

    return {"topic": topic, "data": COMPANY_DATA, "note": "General company information"}


# ── Tool: Search Knowledge Base ───────────────────────────────────────────────

@mcp.tool()
async def search_knowledge_base(
    query: str,
    workspace_id: str | None = None,
    num_results: int = 5,
) -> dict[str, Any]:
    """
    Search the TissaTech knowledge base for relevant information.

    Args:
        query: The search query
        workspace_id: Tenant workspace ID (required for isolated retrieval)
        num_results: Number of results to return (1-10)

    Returns:
        List of relevant knowledge base excerpts with source citations
    """
    from app.agents.bedrock_client import bedrock_client

    num_results = max(1, min(10, num_results))
    if not workspace_id:
        return {
            "query": query,
            "results": [],
            "count": 0,
            "error": "workspace_id is required for isolated retrieval",
        }

    try:
        results = await bedrock_client.search_knowledge_base(
            query,
            num_results,
            workspace_id=workspace_id,
        )
        return {
            "query": query,
            "results": results,
            "count": len(results),
        }
    except Exception as e:
        log.error("mcp.kb_search_failed", error=str(e), query=query)
        return {"query": query, "results": [], "count": 0, "error": "Knowledge base unavailable"}


# ── Tool: Get Current Date/Time ────────────────────────────────────────────────

@mcp.tool()
async def get_current_datetime(timezone: str = "UTC") -> dict[str, str]:
    """
    Get the current date and time.

    Args:
        timezone: Timezone name (e.g., "Asia/Kolkata", "UTC")

    Returns:
        Current date and time information
    """
    now = datetime.utcnow()
    return {
        "datetime": now.isoformat(),
        "date": now.strftime("%B %d, %Y"),
        "time": now.strftime("%H:%M UTC"),
        "day_of_week": now.strftime("%A"),
    }


# ── Tool: Escalate to Human ───────────────────────────────────────────────────

@mcp.tool()
async def escalate_to_human(
    conversation_id: str,
    reason: str,
    priority: str = "normal",
) -> dict[str, Any]:
    """
    Escalate a conversation to a human support agent.

    Args:
        conversation_id: The conversation UUID
        reason: Why escalation is needed
        priority: "low", "normal", or "high"

    Returns:
        Escalation confirmation with ticket ID
    """
    import uuid as _uuid

    ticket_id = f"TKT-{_uuid.uuid4().hex[:8].upper()}"

    # In production: create ticket in your CRM/helpdesk system
    log.info("conversation.escalated",
             conversation_id=conversation_id,
             reason=reason,
             priority=priority,
             ticket_id=ticket_id)

    return {
        "escalated": True,
        "ticket_id": ticket_id,
        "message": f"Your request has been escalated. Ticket #{ticket_id}. A team member will reach out within 24 hours.",
        "priority": priority,
        "estimated_response": "24 hours" if priority == "normal" else "4 hours",
    }


# ── Tool: Submit Lead / Contact Form ──────────────────────────────────────────

@mcp.tool()
async def submit_contact_request(
    name: str,
    email: str,
    subject: str,
    message: str,
) -> dict[str, Any]:
    """
    Submit a contact/lead request on behalf of the user.

    Args:
        name: User's full name
        email: User's email address
        subject: Request subject
        message: Detailed message

    Returns:
        Confirmation with reference number
    """
    import re
    import uuid as _uuid

    # Basic email validation
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return {"success": False, "error": "Invalid email address"}

    ref = f"REF-{_uuid.uuid4().hex[:8].upper()}"

    # In production: save to DB, send to CRM, trigger email
    log.info("lead.captured",
             name=name,
             email=email,
             subject=subject,
             ref=ref)

    return {
        "success": True,
        "reference": ref,
        "message": f"Thank you {name}! We've received your request. Reference: {ref}",
    }


# ── Tool: Check Service Status ────────────────────────────────────────────────

@mcp.tool()
async def check_service_status() -> dict[str, Any]:
    """
    Check the operational status of TissaTech services.

    Returns:
        Status of all services
    """
    # In production: query your status page API
    return {
        "status": "operational",
        "services": {
            "website": "operational",
            "api": "operational",
            "support": "operational",
        },
        "last_updated": datetime.utcnow().isoformat(),
    }


def run_mcp_server():
    """Run the FastMCP server (called from main or separate process)."""
    mcp.run(transport="sse")


if __name__ == "__main__":
    run_mcp_server()
