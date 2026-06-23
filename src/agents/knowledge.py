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
        instructions=(
            "You are the Knowledge specialist. Answer product and documentation questions "
            "using Azure AI Search grounding from the configured index. If the index is not "
            "ready, explain that the Azure AI Search configuration is a placeholder and then "
            "hand control back to the coordinator."
        ),
        context_providers=[search_provider],
        default_options={"store": False},
    )
