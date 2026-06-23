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
- coordinator: yourself — select this when a specialist has already provided an answer
  and you need to deliver the final response to the user.

Guidelines:
- Analyze the user's request and select the appropriate specialist as next speaker.
- After a specialist responds with results, select "coordinator" as next speaker
  so you can synthesize and deliver the final answer to the user.
- If the request is a greeting or general question not matching any specialist,
  select "coordinator" immediately to respond directly.
- When you speak as a participant (not as selector), provide a clear, helpful final
  answer incorporating the specialist's results. Include relevant data from their response.
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
        description="Synthesizes specialist results into a final user-facing answer",
        instructions=(
            "When selected as speaker, provide the final answer to the user. "
            "Use the information from the specialist's previous response to give a clear, "
            "complete, and helpful reply. Include specific data (numbers, IDs, statuses) "
            "from the specialist's output. If the request was a greeting or general question, "
            "respond directly listing available services."
        ),
        client=client,
    )

    # Orchestrator: selects next speaker (uses COORDINATOR_INSTRUCTIONS)
    orchestrator = Agent(
        name="orchestrator",
        description="Selects which specialist or coordinator speaks next",
        instructions=COORDINATOR_INSTRUCTIONS,
        client=client,
    )

    workflow = (
        GroupChatBuilder(
            participants=[billing_agent, iam_agent, ticket_agent, knowledge_agent, coordinator],
            termination_condition=lambda msgs: (
                len(msgs) > 0
                and msgs[-1].author_name == "coordinator"
                and msgs[-1].role == "assistant"
            ),
            orchestrator_agent=orchestrator,
        )
        .build()
    )

    workflow_agent = workflow.as_agent()
    server = ResponsesHostServer(workflow_agent)
    await server.run_async()


if __name__ == "__main__":
    asyncio.run(main())



