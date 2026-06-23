from __future__ import annotations

import os
from typing import Any

from agent_framework import Agent, ToolTypes


def create_ticket_agent(client: Any) -> Agent:
    github_pat = os.environ["GITHUB_PAT"]
    tools: list[ToolTypes] = [
        client.get_mcp_tool(
            name="GitHubIssues",
            url="https://api.githubcopilot.com/mcp/x/issues",
            headers={"Authorization": f"Bearer {github_pat}"},
            approval_mode="never_require",
        )
    ]
    return Agent(
        name="ticket_specialist",
        client=client,
        instructions=(
            "You are the Ticket specialist. Manage GitHub issues as support or work tickets "
            "using only the GitHub issues MCP tool.\n\n"
            "IMPORTANT: Always use the repository 'dsanchor/specialist-mesh' (owner: dsanchor, repo: specialist-mesh) "
            "when creating, listing, or updating issues.\n\n"
            "When creating a ticket, use ONLY the information the user explicitly requests to include. "
            "Do NOT dump the entire conversation history into the ticket. If the user says "
            "'create a ticket about X', the ticket should be about X and nothing else.\n\n"
            "Create, list, update, and manage issues. Be concise and direct in your response."
        ),
        tools=tools,
        default_options={"store": False},
    )
