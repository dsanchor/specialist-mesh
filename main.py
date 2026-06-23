from __future__ import annotations

import asyncio
import os

from agent_framework import Agent, AgentExecutor
from agent_framework.foundry import FoundryChatClient
from agent_framework.observability import get_tracer
from agent_framework.orchestrations import GroupChatBuilder
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from opentelemetry.trace import SpanKind

from agents import (
    create_billing_agent,
    create_iam_agent,
    create_knowledge_agent,
    create_ticket_agent,
)

tracer = get_tracer()

ORCHESTRATOR_INSTRUCTIONS = """
You coordinate a team of specialist agents to solve the user's request.

Available specialists:
- billing_specialist: invoicing, payments, account balance, billing history, refunds
- iam_specialist: password reset/change, user accounts, roles, permissions
- ticket_specialist: create/manage GitHub issues as support tickets
- knowledge_specialist: product documentation, knowledge base queries

Guidelines:
- Route the user's request to the ONE most appropriate specialist.
- If the request is a greeting or general question, respond directly with available services:
  Billing, Identity & Access (IAM), Tickets, and Knowledge Base.
- Once the specialist has responded, synthesize a final user-facing answer using their data.
- Always respond in the same language the user used.
- NEVER ask follow-up questions or suggest next steps. Just answer what was asked.
"""


class TracedAgentExecutor(AgentExecutor):
    """AgentExecutor that wraps agent execution in a custom OTEL span."""

    async def _run_agent_and_emit(self, ctx):
        with tracer.start_as_current_span(
            f"specialist.{self.id}",
            kind=SpanKind.INTERNAL,
            attributes={
                "agent.name": self.id,
                "agent.type": "specialist",
                "gen_ai.agent.name": self.id,
            },
        ):
            return await super()._run_agent_and_emit(ctx)


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

    orchestrator_agent = Agent(
        name="orchestrator",
        description="Coordinates specialist agents to solve user requests",
        instructions=ORCHESTRATOR_INSTRUCTIONS,
        client=client,
    )

    participants = [
        TracedAgentExecutor(billing_agent, id=billing_agent.name, context_mode="full"),
        TracedAgentExecutor(iam_agent, id=iam_agent.name, context_mode="full"),
        TracedAgentExecutor(ticket_agent, id=ticket_agent.name, context_mode="full"),
        TracedAgentExecutor(knowledge_agent, id=knowledge_agent.name, context_mode="full"),
    ]

    workflow = (
        GroupChatBuilder(
            participants=participants,
            orchestrator_agent=orchestrator_agent,
            intermediate_output_from=participants,
        )
        .with_termination_condition(
            lambda msgs: sum(1 for m in msgs if m.role == "assistant") >= 4
        )
        .build()
    )

    workflow_agent = workflow.as_agent()
    server = ResponsesHostServer(workflow_agent)
    await server.run_async()


if __name__ == "__main__":
    asyncio.run(main())
