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

    await client.configure_azure_monitor(
        enable_sensitive_data=os.environ.get("ENABLE_SENSITIVE_DATA", "true").lower() == "true",
        enable_live_metrics=True,
    )

    billing_agent = create_billing_agent(client)
    iam_agent = create_iam_agent(client)
    ticket_agent = create_ticket_agent(client)
    knowledge_agent = create_knowledge_agent(client, credential)

    coordinator = Agent(
        name="coordinator",
        client=client,
        instructions=(
            "You are the coordinator for specialist-mesh. Your only job is to identify the "
            "user's intent and route the request to exactly one appropriate specialist via "
            "handoff. Do not perform billing, IAM, ticket, or knowledge work yourself. When "
            "a specialist returns, decide whether another routing step is needed or whether "
            "the request is complete."
        ),
        default_options={"store": False},
        require_per_service_call_history_persistence=True,
    )

    workflow = (
        HandoffBuilder(
            name="specialist_mesh",
            participants=[coordinator, billing_agent, iam_agent, ticket_agent, knowledge_agent],
            termination_condition=(
                "End the workflow after the user's request is fulfilled and control has returned "
                "to the coordinator."
            ),
        )
        .with_start_agent(coordinator)
        .add_handoff(coordinator, [billing_agent, iam_agent, ticket_agent, knowledge_agent])
        .add_handoff(billing_agent, [coordinator])
        .add_handoff(iam_agent, [coordinator])
        .add_handoff(ticket_agent, [coordinator])
        .add_handoff(knowledge_agent, [coordinator])
        .with_autonomous_mode(
            turn_limits={
                resolve_agent_id(coordinator): 12,
                resolve_agent_id(billing_agent): 6,
                resolve_agent_id(iam_agent): 6,
                resolve_agent_id(ticket_agent): 6,
                resolve_agent_id(knowledge_agent): 6,
            }
        )
        .build()
    )

    workflow_agent = workflow.as_agent()
    server = ResponsesHostServer(workflow_agent)
    await server.run_async()


if __name__ == "__main__":
    asyncio.run(main())
