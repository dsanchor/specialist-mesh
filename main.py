from __future__ import annotations

import asyncio
import json
import os
from typing import Literal

from agent_framework import Agent, AgentExecutor, Message
from agent_framework.foundry import FoundryAgent, FoundryChatClient
from agent_framework.orchestrations import GroupChatBuilder, GroupChatOrchestrator, GroupChatState
from agent_framework_orchestrations._base_group_chat_orchestrator import ParticipantRegistry
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from pydantic import BaseModel, Field


ParticipantName = Literal[
    "orchestrator",
    "billing_specialist",
    "iam_specialist",
    "ticket_specialist",
    "knowledge_specialist",
]


class RoutingDecision(BaseModel):
    next_speaker: ParticipantName = Field(description="The participant that should answer the user request")
    reason: str = Field(description="Brief reason for the routing decision")


class SingleTurnGroupChatOrchestrator(GroupChatOrchestrator):
    async def _handle_response(self, response, ctx) -> None:
        messages = self._process_participant_response(response)
        self._append_messages(messages)


def create_foundry_specialist(
    *,
    project_endpoint: str,
    credential: DefaultAzureCredential,
    agent_name: str,
    agent_version: str,
) -> FoundryAgent:
    return FoundryAgent(
        project_endpoint=project_endpoint,
        agent_name=agent_name,
        agent_version=agent_version,
        credential=credential,
    )




ORCHESTRATOR_INSTRUCTIONS = """
Role
- You coordinate a team of specialist agents to solve the user's request.
- You also answer directly when the user's request does not require a specialist.

Available participants
- orchestrator: greetings, general questions, what this agent can do, and requests that do not
    belong to a specialist domain
- billing_specialist: invoicing, payments, account balance, billing history, refunds
- iam_specialist: password reset/change, user accounts, roles, permissions
- ticket_specialist: create/manage GitHub issues as support tickets
- knowledge_specialist: product documentation, knowledge base queries

Routing rules
- For greetings, general questions, capability questions, or requests that do not match any
    specialist domain, select orchestrator and respond immediately.
- Route the user's request to the one most appropriate specialist.
- If the request spans multiple domains, select the specialist that owns the user's primary goal.
- The selected specialist must provide the final user-facing answer directly.
- Do not call a specialist just to answer a greeting, explain available services, or handle a
    general non-domain question.

Response rules
- Always respond in the same language the user used.
- When responding directly as orchestrator, briefly explain that you can help with Billing,
    Identity & Access (IAM), Tickets, and Knowledge Base requests.
- Never ask follow-up questions or suggest next steps unless a specialist tool cannot be used
    without a required identifier or subject.
- Prefer complete, readable answers over very short answers.

Context handling
- When selecting a specialist, include in your reasoning any relevant context from the
  conversation that the specialist might need (e.g., user IDs, invoice numbers, error details
  from previous exchanges). The specialist can see the full conversation history.
"""

ROUTING_INSTRUCTIONS = """
Select exactly one participant to answer the latest user request.

Participants:
- orchestrator: greetings, general questions, what this agent can do, and requests that do not
    belong to a specialist domain
- billing_specialist: invoicing, payments, account balance, billing history, refunds
- iam_specialist: password reset/change, user accounts, roles, permissions
- ticket_specialist: create/manage GitHub issues as support tickets
- knowledge_specialist: product documentation, knowledge base queries

Rules:
- Return orchestrator for greetings, general capability questions, and anything outside the
    specialist domains.
- Return one specialist for domain requests.
- Do not choose multiple participants.
"""


def parse_routing_decision(agent_response) -> RoutingDecision:
        if getattr(agent_response, "value", None) is not None:
                return RoutingDecision.model_validate(agent_response.value)

        text = agent_response.text.strip()
        try:
                return RoutingDecision.model_validate_json(text)
        except ValueError:
                start = text.find("{")
                end = text.rfind("}")
                if start >= 0 and end > start:
                        return RoutingDecision.model_validate(json.loads(text[start : end + 1]))
                raise


async def route_next_speaker(orchestrator_agent: Agent, state: GroupChatState) -> str:
        agent_response = await orchestrator_agent.run(
            messages=[*state.conversation, Message(role="user", contents=[ROUTING_INSTRUCTIONS])],
                options={"response_format": RoutingDecision},
        )
        return parse_routing_decision(agent_response).next_speaker

async def main() -> None:
    load_dotenv()

    project_endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
    credential = DefaultAzureCredential()
    client = FoundryChatClient(
        project_endpoint=project_endpoint,
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=credential,
    )

    orchestrator_agent = Agent(
        name="orchestrator",
        description="Coordinates specialist agents to solve user requests",
        instructions=ORCHESTRATOR_INSTRUCTIONS,
        client=client,
    )

    billing_agent = create_foundry_specialist(
        project_endpoint=project_endpoint,
        credential=credential,
        agent_name="BillingAgent",
        agent_version="3",
    )
    iam_agent = create_foundry_specialist(
        project_endpoint=project_endpoint,
        credential=credential,
        agent_name="IAMAgent",
        agent_version="4",
    )
    ticket_agent = create_foundry_specialist(
        project_endpoint=project_endpoint,
        credential=credential,
        agent_name="TicketingAgent",
        agent_version="3",
    )
    knowledge_agent = create_foundry_specialist(
        project_endpoint=project_endpoint,
        credential=credential,
        agent_name="KnowledgeBaseAgent",
        agent_version="3",
    )

    participants = [
        AgentExecutor(orchestrator_agent, id="orchestrator", context_mode="full"),
        AgentExecutor(billing_agent, id="billing_specialist", context_mode="full"),
        AgentExecutor(iam_agent, id="iam_specialist", context_mode="full"),
        AgentExecutor(ticket_agent, id="ticket_specialist", context_mode="full"),
        AgentExecutor(knowledge_agent, id="knowledge_specialist", context_mode="full"),
    ]

    orchestrator = SingleTurnGroupChatOrchestrator(
        id="group_chat_orchestrator",
        participant_registry=ParticipantRegistry(participants),
        selection_func=lambda state: route_next_speaker(orchestrator_agent, state),
        name="orchestrator",
        max_rounds=1,
    )

    workflow = (
        GroupChatBuilder(
            participants=participants,
            orchestrator=orchestrator,
            output_from="all",
        )
        .build()
    )

    workflow_agent = workflow.as_agent()
    server = ResponsesHostServer(workflow_agent)
    await server.run_async()


if __name__ == "__main__":
    asyncio.run(main())
