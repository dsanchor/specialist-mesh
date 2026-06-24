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


class TracedAgentExecutor(AgentExecutor):
    """AgentExecutor that wraps agent execution with correct gen_ai.agent.name in OTEL spans."""

    async def _run_agent_and_emit(self, ctx):
        with tracer.start_as_current_span(
            f"invoke_agent {self.id}",
            kind=SpanKind.INTERNAL,
            attributes={
                "gen_ai.agent.name": self.id,
                "gen_ai.agent.id": self.id,
                "agent.name": self.id,
            },
        ):
            await super()._run_agent_and_emit(ctx)


ORCHESTRATOR_INSTRUCTIONS = """
Role
- You coordinate a team of specialist agents to solve the user's request.

Available specialists
- billing_specialist: invoicing, payments, account balance, billing history, refunds
- iam_specialist: password reset/change, user accounts, roles, permissions
- ticket_specialist: create/manage GitHub issues as support tickets
- knowledge_specialist: product documentation, knowledge base queries
- coordinator: final user-facing response synthesis

Routing rules
- Route the user's request to the one most appropriate specialist.
- If the request is a greeting or general question, select coordinator.
- Once the specialist has responded, select coordinator so it can provide the final user-facing answer.

Response rules
- Always respond in the same language the user used.
- NEVER ask follow-up questions or suggest next steps. Just answer what was asked.

Context handling
- When selecting a specialist, include in your reasoning any relevant context from the
  conversation that the specialist might need (e.g., user IDs, invoice numbers, error details
  from previous exchanges). The specialist can see the full conversation history.
"""

COORDINATOR_INSTRUCTIONS = """
Role
- You are the final responder for the user.

When selected for a greeting or general question
- If selected for a greeting or general question, reply directly and list available services:
    Billing, Identity & Access (IAM), Tickets, and Knowledge Base.

When selected after a specialist
- If selected after a specialist response, provide a concise final answer using the specialist data.

Response rules
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
        TracedAgentExecutor(billing_agent, id=billing_agent.name, context_mode="full"),
        TracedAgentExecutor(iam_agent, id=iam_agent.name, context_mode="full"),
        TracedAgentExecutor(ticket_agent, id=ticket_agent.name, context_mode="full"),
        TracedAgentExecutor(knowledge_agent, id=knowledge_agent.name, context_mode="full"),
        TracedAgentExecutor(coordinator_agent, id=coordinator_agent.name, context_mode="full"),
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
