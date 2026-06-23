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

COORDINATOR_INSTRUCTIONS = """
You coordinate a team of specialist agents to resolve user requests.

Available specialists:
- billing_specialist: invoicing, payments, account balance, billing history, refunds
- iam_specialist: password reset/change, user accounts, roles, permissions
- ticket_specialist: create/manage GitHub issues as support tickets
- knowledge_specialist: product documentation, knowledge base queries

Guidelines:
- Analyze the user's request and route to the appropriate specialist.
- After a specialist responds, evaluate if the answer is complete.
- If more information is needed, route to the same or another specialist.
- Once you have a satisfactory answer, provide a final summary to the user.
- If the request is a greeting or general question not matching any specialist,
  respond directly with a friendly answer listing available services.
- Always finish the conversation — do not leave it hanging.
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

    coordinator = Agent(
        name="coordinator",
        description="Coordinates multi-agent collaboration by selecting the right specialist",
        instructions=COORDINATOR_INSTRUCTIONS,
        client=client,
    )

    workflow = (
        GroupChatBuilder(
            participants=[billing_agent, iam_agent, ticket_agent, knowledge_agent],
            termination_condition=lambda msgs: sum(1 for m in msgs if m.role == "assistant") >= 10,
            orchestrator_agent=coordinator,
        )
        .build()
    )

    workflow_agent = workflow.as_agent()
    server = ResponsesHostServer(workflow_agent)
    await server.run_async()


if __name__ == "__main__":
    asyncio.run(main())



