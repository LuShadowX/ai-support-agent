"""Tools the agent can call. Each tool = a JSON schema (what the LLM sees) + a Python function (what runs).

To add a tool for a client: add a schema to TOOL_SCHEMAS and a method named `_<tool_name>` below.
"""

import json
import logging

from app.db import Database
from app.knowledge import KnowledgeBase

log = logging.getLogger(__name__)

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": "Search the company's documents (FAQ, policies, product info). "
                           "Use this before answering ANY question about the business.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "A focused search query in English."}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_order",
            "description": "Get status, items and tracking for an order. Requires BOTH the order ID and the email used to place it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "e.g. NH-1001"},
                    "email": {"type": "string"},
                },
                "required": ["order_id", "email"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_product",
            "description": "Get the live price and stock level of a product by name or SKU.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Product name or SKU"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_support_ticket",
            "description": "Hand the conversation to a human agent. Use when the customer asks for a human, "
                           "when you cannot answer, or for refunds/complaints. Collect name and email first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "email": {"type": "string"},
                    "summary": {"type": "string", "description": "One or two sentences describing the issue."},
                },
                "required": ["name", "email", "summary"],
            },
        },
    },
]


class ToolRunner:
    def __init__(self, kb: KnowledgeBase, db: Database, top_k: int):
        self._kb = kb
        self._db = db
        self._top_k = top_k

    def run(self, name: str, raw_arguments: str, session_id: str) -> dict:
        """Execute a tool call from the LLM. Never raises: errors go back to the LLM as data."""
        handler = getattr(self, f"_{name}", None)
        if handler is None:
            return {"error": f"Unknown tool: {name}"}
        try:
            args = json.loads(raw_arguments or "{}")
            return handler(session_id=session_id, **args)
        except (json.JSONDecodeError, TypeError) as exc:
            return {"error": f"Invalid arguments: {exc}"}
        except Exception:
            log.exception("Tool %s failed", name)
            return {"error": "The tool failed. Apologise and offer to connect the customer with the team."}

    def _search_knowledge_base(self, session_id: str, query: str) -> dict:
        results = self._kb.search(query, self._top_k)
        if not results:
            return {"results": [], "note": "Nothing relevant found in the documents."}
        return {"results": results}

    def _lookup_order(self, session_id: str, order_id: str, email: str) -> dict:
        order = self._db.get_order(order_id, email)
        if order is None:
            return {"found": False, "note": "No order matches that order ID and email combination."}
        order.pop("email", None)
        return {"found": True, "order": order}

    def _check_product(self, session_id: str, query: str) -> dict:
        products = self._db.find_products(query)
        return {"products": products} if products else {"products": [], "note": "No matching product."}

    def _create_support_ticket(self, session_id: str, name: str, email: str, summary: str) -> dict:
        ticket_id = self._db.create_ticket(session_id, name, email, summary)
        return {"ticket_id": ticket_id, "note": "A team member will reply by email within 1 business day."}
