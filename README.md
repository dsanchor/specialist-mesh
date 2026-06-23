# Specialist Mesh

A multi-agent orchestration system built with Microsoft Agent Framework (Python) that routes user requests to specialized agents via a coordinator using handoff patterns.

## Architecture

Specialist Mesh implements a **Coordinator + 4 Specialists** pattern:

```
┌─────────────────────────────────────────────────┐
│        User Request (Natural Language)          │
└─────────────────────────┬───────────────────────┘
                          │
                    ┌─────▼─────┐
                    │ Coordinator│ (Intent Detection & Routing)
                    └─────┬─────┘
       ┌────────────┬─────┴──────┬──────────────┐
       │            │            │              │
   ┌───▼────┐  ┌───▼────┐  ┌───▼────┐  ┌───▼──────┐
   │Billing │  │  IAM   │  │Ticket  │  │Knowledge │
   │ Agent  │  │ Agent  │  │ Agent  │  │ Agent    │
   │(10t)   │  │ (8t)   │  │(MCP)   │  │(RAG)     │
   └────────┘  └────────┘  └────────┘  └──────────┘
```

### Agents

- **Coordinator**: Detects intent and routes requests to specialists. Performs no domain work—purely orchestration.
- **Billing Agent**: 10 tools for invoice management, payment processing, account balance queries, and billing history.
- **IAM Agent**: 8 tools for user lifecycle management, password resets, role assignment, and permission auditing.
- **Ticket Agent**: GitHub Issues integration via MCP server (remote server at `api.githubcopilot.com`).
- **Knowledge Agent**: Azure AI Search RAG for documentation and product knowledge queries.

## Key Features

- **HandoffBuilder with Autonomous Mode**: Agents autonomously route between specialists via handoff patterns without explicit coordinator intervention for follow-up requests.
- **OTEL Observability**: OpenTelemetry traces automatically exported to Azure Monitor / App Insights connected to your Foundry project.
- **Hosted Agent Deployment**: Deploy as a response API in Azure AI Foundry with streamlined containerization.
- **MCP Integration**: GitHub Issues support via the open-source MCP server for advanced ticket management.
- **RAG Context Provider**: Azure AI Search integration for grounding Knowledge Agent responses in product documentation.

## Project Structure

```
src/
├── main.py                    # Entry point and coordinator setup
├── requirements.txt           # Python dependencies
├── .env.example              # Configuration template
├── agent.yaml                # Agent definition (Foundry deployment)
├── agent.manifest.yaml       # Agent manifest with metadata
├── Dockerfile                # Container image (python:3.12-slim, port 8088)
└── agents/
    ├── __init__.py
    ├── billing.py            # Billing specialist agent
    ├── iam.py                # IAM specialist agent
    ├── ticket.py             # GitHub Issues specialist agent
    ├── knowledge.py          # Knowledge/RAG specialist agent
    └── coordinator.py        # Coordinator and routing logic
```

## Prerequisites

- **Python 3.12+**
- **Azure AI Foundry Project** with Azure Application Insights enabled
- **Azure AI Search Service** (for the Knowledge agent)
- **GitHub Personal Access Token** (PAT) with `repo:issues` scope (for the Ticket agent)
- **Docker** (optional, for local containerization testing)

## Configuration

Configuration is managed via environment variables in a `.env` file. Copy `.env.example` to `.env` and fill in your values:

```bash
cd src
cp .env.example .env
# Edit .env with your credentials and endpoints
```

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `FOUNDRY_PROJECT_ENDPOINT` | Azure AI Foundry project endpoint | `https://your-project.services.ai.azure.com/api/projects/your-project` |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | LLM deployment name in Foundry | `gpt-5.4-mini` |
| `GITHUB_PAT` | GitHub Personal Access Token | `ghp_xxxxxxxxxxxx` |
| `AZURE_SEARCH_ENDPOINT` | Azure AI Search service endpoint | `https://your-search.search.windows.net` |
| `AZURE_SEARCH_INDEX_NAME` | Search index for RAG | `your-index-name` |
| `ENABLE_SENSITIVE_DATA` | Include sensitive info in logs | `true` or `false` |

## Local Development

Run the specialist mesh locally:

```bash
cd src

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Run the coordinator
python main.py
```

The coordinator will start and wait for user requests. It automatically initializes all specialists and sets up handoff routing.

## Deployment

Deploy as a hosted agent in Azure AI Foundry:

```bash
# From the project root
azd ai agent create
```

### What Happens

1. **agent.yaml** defines the agent configuration (name, model, system prompt, tools).
2. **agent.manifest.yaml** provides metadata for the Foundry hosting.
3. **Dockerfile** packages the application in a `python:3.12-slim` container (exposed on port 8088).
4. Foundry handles routing of requests to the Response API and automatic scaling.

For more details on Foundry deployment, see the [Azure AI Foundry documentation](https://learn.microsoft.com/en-us/azure/ai-foundry/).

## Observability

All agent invocations, tool calls, and handoffs are traced via OpenTelemetry and automatically exported to the Azure Application Insights instance linked to your Foundry project. Traces include:

- **Agent invocations**: Start/end times, input/output, status
- **Tool calls**: Tool name, parameters, results, duration
- **Handoffs**: Source agent, target agent, handoff reason
- **Errors**: Full stack traces and context

View traces in the Azure Portal under your Application Insights resource, or via the Foundry project dashboard.

## References

- [Microsoft Agent Framework (Python)](https://github.com/microsoft/agent-framework/tree/main/python)
- [GitHub MCP Server](https://github.com/github/github-mcp-server)
- [Azure AI Search Documentation](https://learn.microsoft.com/en-us/azure/search/)
- [Azure AI Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry/)
- [OpenTelemetry Python](https://opentelemetry.io/docs/instrumentation/python/)

## License

See LICENSE file in the repository.
