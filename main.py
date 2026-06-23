from __future__ import annotations

import asyncio
import os

from agent_framework import Agent, resolve_agent_id
from agent_framework.foundry import FoundryChatClient
from agent_framework.orchestrations import HandoffBuilder
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

from agents import (
    create_billing_agent,
    create_iam_agent,
    create_knowledge_agent,
    create_ticket_agent,
)


async def main() -> None:
    load_dotenv()

    credential = DefaultAzureCredential()
    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=credential,
    )

    # Observability (OTEL → App Insights) is auto-configured by the Foundry
    # hosting infrastructure via agent.yaml ENABLE_SENSITIVE_DATA setting.
    # No manual configure_azure_monitor() call needed for hosted agents.

    billing_agent = create_billing_agent(client)
    iam_agent = create_iam_agent(client)
    ticket_agent = create_ticket_agent(client)
    knowledge_agent = create_knowledge_agent(client, credential)

    coordinator = Agent(
        name="coordinator",
        client=client,
        id="specialist-mesh-coordinator",
        instructions=(
            "You are the coordinator for specialist-mesh. Your job is to identify the user's "
            "intent and route the request to the appropriate specialist via handoff.\n\n"
            "Available specialists:\n"
            "- billing_specialist: invoicing, payments, account balance, billing history\n"
            "- iam_specialist: password reset/change, user accounts, roles, permissions\n"
            "- ticket_specialist: create/manage GitHub issues as support tickets\n"
            "- knowledge_specialist: product documentation, knowledge base queries\n\n"
            "IMPORTANT RULES:\n"
            "1. If the user's message clearly maps to a specialist, hand off immediately.\n"
            "2. If the message is a greeting, general question, or does NOT match any specialist, "
            "respond directly with a brief friendly answer and list the services you offer. "
            "Do NOT keep iterating — one response is enough.\n"
            "3. When a specialist returns control to you, provide the final summary to the user."
        ),
        default_options={"store": False},
        require_per_service_call_history_persistence=True,
    )

    workflow = (
        HandoffBuilder(
            name="specialist_mesh",
            participants=[coordinator, billing_agent, iam_agent, ticket_agent, knowledge_agent],
            termination_condition=lambda conv: (
                sum(1 for msg in conv if msg.author_name == "coordinator" and msg.role == "assistant") >= 10
            ),
        )
        .with_start_agent(coordinator)
        .add_handoff(coordinator, [billing_agent, iam_agent, ticket_agent, knowledge_agent])
        .add_handoff(billing_agent, [coordinator])
        .add_handoff(iam_agent, [coordinator])
        .add_handoff(ticket_agent, [coordinator])
        .add_handoff(knowledge_agent, [coordinator])
        .build()
    )

    workflow_agent = workflow.as_agent()
    server = ResponsesHostServer(workflow_agent)
    await server.run_async()


if __name__ == "__main__":
    asyncio.run(main())
