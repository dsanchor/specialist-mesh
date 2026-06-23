from __future__ import annotations

import asyncio
import os

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework.orchestrations import MagenticBuilder
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

from agents import (
    create_billing_agent,
    create_iam_agent,
    create_knowledge_agent,
    create_ticket_agent,
)

MANAGER_INSTRUCTIONS = """
You coordinate a team of specialist agents to resolve user requests efficiently.

Available specialists:
- billing_specialist: invoicing, payments, account balance, billing history, refunds
- iam_specialist: password reset/change, user accounts, roles, permissions
- ticket_specialist: create/manage GitHub issues as support tickets
- knowledge_specialist: product documentation, knowledge base queries

Guidelines:
- Analyze the user's request and identify ALL domains involved.
- Delegate to each required specialist. If the request spans multiple domains,
  call each specialist sequentially until all parts are covered.
- Once all specialists have provided their data, synthesize a final comprehensive
  answer incorporating all results.
- If the request is a greeting or general question, respond directly.
"""


async def main() -> None:
    load_dotenv()

    credential = DefaultAzureCredential()
    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=credential,
    )

    billing_agent = create_billing_agent(client)
    iam_agent = create_iam_agent(client)
    ticket_agent = create_ticket_agent(client)
    knowledge_agent = create_knowledge_agent(client, credential)

    manager = Agent(
        name="manager",
        description="Orchestrator that coordinates specialist agents and synthesizes final answers",
        instructions=MANAGER_INSTRUCTIONS,
        client=client,
    )

    workflow = MagenticBuilder(
        participants=[billing_agent, iam_agent, ticket_agent, knowledge_agent],
        manager_agent=manager,
        max_round_count=10,
        max_stall_count=3,
        max_reset_count=2,
    ).build()

    workflow_agent = workflow.as_agent()
    server = ResponsesHostServer(workflow_agent)
    await server.run_async()


if __name__ == "__main__":
    asyncio.run(main())




