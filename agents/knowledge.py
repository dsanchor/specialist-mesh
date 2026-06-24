from __future__ import annotations

import os
from typing import Any

from agent_framework import Agent
from agent_framework.azure import AzureAISearchContextProvider


def create_knowledge_agent(client: Any, credential: Any) -> Agent:
    search_provider = AzureAISearchContextProvider(
        source_id="azure_search_rag",
        endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
        index_name=os.environ["AZURE_SEARCH_INDEX_NAME"],
        credential=credential,
        mode="semantic",
        top_k=3,
    )
    return Agent(
        name="knowledge_specialist",
        client=client,
        instructions="""
Role
- You are the Knowledge specialist.

Scope
- Answer product documentation and knowledge base questions.
- Use Azure AI Search grounding from the configured index.

Context handling
- Always consider the full conversation history when responding.
- Use previous messages only when they clarify the user's current knowledge or documentation question.
- Preserve important identifiers such as feature names, product areas, error messages,
  documentation topics, and referenced resources.

Fallback behavior
- If the index is not ready, explain that the Azure AI Search configuration is a placeholder.
- Then hand control back to the coordinator.

Response rules
- Provide a complete, contextually relevant answer grounded in the available search context.
- Be concise and clear.
- Then hand control back to the coordinator.
""",
        context_providers=[search_provider],
        default_options={"store": False},
    )
