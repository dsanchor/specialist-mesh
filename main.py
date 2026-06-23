from __future__ import annotations

import asyncio
import os

from agent_framework import Agent
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

# ---------------------------------------------------------------------------
# Monkey-patch: extend checkpoint allowed types at the CLASS level so that
# ALL instances of FileCheckpointStorage automatically permit the types
# needed by HandoffBuilder workflows. The hosting package's allowlist is too
# narrow for orchestration checkpoints.
# ---------------------------------------------------------------------------
from agent_framework._workflows._checkpoint import FileCheckpointStorage
from agent_framework._workflows import _checkpoint_encoding

_EXTRA_ALLOWED_TYPES = frozenset([
    "agent_framework_orchestrations._handoff:HandoffAgentUserRequest",
    "types:GenericAlias",
])

# Patch the RestrictedUnpickler to also allow agent_framework_orchestrations.*
# and common stdlib types needed for checkpoint serialization.
_original_find_class = _checkpoint_encoding._RestrictedUnpickler.find_class


def _patched_find_class(self, module: str, name: str):
    type_key = f"{module}:{name}"
    # Allow orchestrations package and common Python types used in generics
    if (
        module.startswith("agent_framework_orchestrations")
        or type_key in _EXTRA_ALLOWED_TYPES
    ):
        import importlib
        mod = importlib.import_module(module)
        return getattr(mod, name)
    return _original_find_class(self, module, name)


_checkpoint_encoding._RestrictedUnpickler.find_class = _patched_find_class
# ---------------------------------------------------------------------------


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
        client=client,
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
        require_per_service_call_history_persistence=True,
    )

    workflow = (
        HandoffBuilder(
            name="specialist_mesh",
            participants=[coordinator, billing_agent, iam_agent, ticket_agent, knowledge_agent],
            termination_condition=lambda conv: (
                len(conv) > 0
                and conv[-1].author_name == "coordinator"
                and conv[-1].role == "assistant"
                and any(
                    word in (conv[-1].text or "").lower()
                    for word in ["help you", "assist you", "anything else", "you're welcome"]
                )
            ),
        )
        .with_start_agent(coordinator)
        .build()
    )

    workflow_agent = workflow.as_agent()
    server = ResponsesHostServer(workflow_agent)
    await server.run_async()


if __name__ == "__main__":
    asyncio.run(main())

