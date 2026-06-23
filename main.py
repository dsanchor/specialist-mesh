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

COORDINATOR_INSTRUCTIONS = """
You are the orchestrator for a multi-agent system. Your ONLY job is to select which agent speaks next.

Available agents to select:
- billing_specialist: invoicing, payments, account balance, billing history, refunds
- iam_specialist: password reset/change, user accounts, roles, permissions
- ticket_specialist: create/manage GitHub issues as support tickets
- knowledge_specialist: product documentation, knowledge base queries
- coordinator: delivers the final answer to the user

DECISION PROCESS:
1. Identify which ONE specialist best matches the user's request.
2. Select that specialist.
3. Once the specialist has responded, select "coordinator" to deliver the answer.
4. If the request is a greeting or general question, select "coordinator" directly.
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

    orchestrator = Agent(
        name="orchestrator",
        description="Selects which specialist or coordinator speaks next",
        instructions=COORDINATOR_INSTRUCTIONS,
        client=client,
    )

    # Wrap each agent in TracedAgentExecutor for custom OTEL spans
    # context_mode="full" ensures specialists receive the entire conversation history
    participants = [
        TracedAgentExecutor(billing_agent, id=billing_agent.name, context_mode="full"),
        TracedAgentExecutor(iam_agent, id=iam_agent.name, context_mode="full"),
        TracedAgentExecutor(ticket_agent, id=ticket_agent.name, context_mode="full"),
        TracedAgentExecutor(knowledge_agent, id=knowledge_agent.name, context_mode="full"),
        TracedAgentExecutor(coordinator, id=coordinator.name, context_mode="full"),
    ]

    def termination_condition(msgs: list) -> bool:
        """Terminate when coordinator speaks after the last user message."""
        # Find the last user message index
        last_user_idx = -1
        for i, m in enumerate(msgs):
            if m.role == "user":
                last_user_idx = i
        # Check if coordinator spoke after the last user message
        for m in msgs[last_user_idx + 1:]:
            if m.role == "assistant" and m.author_name == "coordinator":
                return True
        return False

    workflow = (
        GroupChatBuilder(
            participants=participants,
            termination_condition=termination_condition,
            orchestrator_agent=orchestrator,
        )
        .build()
    )

    workflow_agent = workflow.as_agent()
    server = ResponsesHostServer(workflow_agent)
    await server.run_async()


if __name__ == "__main__":
    asyncio.run(main())

