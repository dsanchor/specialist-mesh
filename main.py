from __future__ import annotations

import asyncio
import os

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework.orchestrations import GroupChatBuilder
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

from agents import (
    create_billing_agent,
    create_iam_agent,
    create_knowledge_agent,
    create_ticket_agent,
)

ORCHESTRATOR_INSTRUCTIONS = """
You coordinate a team of specialist agents to solve the user's request.

Available specialists:
- billing_specialist: invoicing, payments, account balance, billing history, refunds
- iam_specialist: password reset/change, user accounts, roles, permissions
- ticket_specialist: create/manage GitHub issues as support tickets
- knowledge_specialist: product documentation, knowledge base queries

Guidelines:
- Route the user's request to the ONE most appropriate specialist.
- If the request is a greeting or general question, select coordinator.
- Once the specialist has responded, select coordinator so it can provide the final user-facing answer.
- Always respond in the same language the user used.
- NEVER ask follow-up questions or suggest next steps. Just answer what was asked.
- When selecting a specialist, include in your reasoning any relevant context from the
  conversation that the specialist might need (e.g., user IDs, invoice numbers, error details
  from previous exchanges). The specialist can see the full conversation history.
"""

COORDINATOR_INSTRUCTIONS = """
You are the final responder for the user.

Rules:
- If selected for a greeting or general question, reply directly and list available services:
    Billing, Identity & Access (IAM), Tickets, and Knowledge Base.
- If selected after a specialist response, provide a concise final answer using the specialist data.
- Always respond in the same language as the user.
- Do not ask follow-up questions and do not suggest next steps.
"""

async def main() -> None:
    load_dotenv()

    credential = DefaultAzureCredential()
    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=credential,
    )

    orchestrator_agent = Agent(
        name="orchestrator",
        description="Coordinates specialist agents to solve user requests",
        instructions=ORCHESTRATOR_INSTRUCTIONS,
        client=client,
    )

    coordinator_agent = Agent(
        name="coordinator",
        description="Delivers the final response to the user",
        instructions=COORDINATOR_INSTRUCTIONS,
        client=client,
    )

    billing_agent = create_billing_agent(client)
    iam_agent = create_iam_agent(client)
    ticket_agent = create_ticket_agent(client)
    knowledge_agent = create_knowledge_agent(client, credential)

    participants = [
        billing_agent,
        iam_agent,
        ticket_agent,
        knowledge_agent,
        coordinator_agent,
    ]

    workflow = (
        GroupChatBuilder(
            participants=participants,
            orchestrator_agent=orchestrator_agent,
        )
        .build()
    )

    workflow_agent = workflow.as_agent()
    server = ResponsesHostServer(workflow_agent)
    await server.run_async()


if __name__ == "__main__":
    asyncio.run(main())
