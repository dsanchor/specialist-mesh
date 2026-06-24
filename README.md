# Specialist Mesh

A multi-agent orchestration system built with Microsoft Agent Framework (Python) that routes user requests to specialized agents through a group chat orchestrator and returns a synthesized user-facing response.

## Architecture

Specialist Mesh implements an **Orchestrator + Coordinator + 4 Specialists** pattern:

```
┌─────────────────────────────────────────────────┐
│        User Request (Natural Language)          │
└─────────────────────────┬───────────────────────┘
                          │
                    ┌─────▼──────┐
                    │Orchestrator│ (Intent Detection & Speaker Selection)
                    └─────┬──────┘
       ┌────────────┬─────┴──────┬──────────────┬──────────────┐
       │            │            │              │              │
   ┌───▼────┐  ┌────▼───┐  ┌────▼───┐  ┌───────▼──┐  ┌────────▼───┐
   │Billing │  │  IAM   │  │Ticket  │  │Knowledge │  │Coordinator │
   │ Agent  │  │ Agent  │  │ Agent  │  │ Agent    │  │  Response  │
   │(10t)   │  │ (9t)   │  │(MCP)   │  │(Search)  │  │ Synthesis  │
   └────────┘  └────────┘  └────────┘  └──────────┘  └────────────┘
```

### Agents

- **Orchestrator**: Selects the appropriate specialist, or selects the coordinator for greetings/general requests and final response synthesis.
- **Coordinator**: Delivers the final user-facing response using specialist output. It does not perform domain tool work.
- **Billing Agent**: 10 tools for invoice management, payment processing, account balance queries, and billing history.
- **IAM Agent**: 9 tools for user lifecycle management, password resets/changes, role assignment, and permission auditing.
- **Ticket Agent**: GitHub Issues integration via MCP server at `https://api.githubcopilot.com/mcp/x/issues`.
- **Knowledge Agent**: Azure AI Search context provider for documentation and product knowledge queries.

## Key Features

- **GroupChatBuilder Orchestration**: The default entry point uses a group chat workflow with an orchestrator agent that chooses the next speaker and a coordinator agent that synthesizes final responses.
- **Custom OTEL Spans**: Specialist execution is wrapped with OpenTelemetry spans that set agent-specific attributes such as `gen_ai.agent.name`.
- **Hosted Agent Deployment**: Deploy as a response API in Azure AI Foundry with streamlined containerization.
- **MCP Integration**: GitHub Issues support through the GitHub Copilot MCP endpoint for ticket management.
- **Azure AI Search Context Provider**: Search-backed grounding for Knowledge Agent responses.

## Project Structure

```
.
├── main.py                    # Default hosted group chat entry point
├── requirements.txt           # Python dependencies
├── .env.example               # Configuration template
├── agent.yaml                 # Hosted agent definition
├── agent.manifest.yaml        # Hosted agent manifest and model resource metadata
├── Dockerfile                 # Container image (Python 3.12 devcontainer base, port 8088)
└── agents/
    ├── __init__.py
    ├── billing.py             # Billing specialist agent and 10 local tools
    ├── iam.py                 # IAM specialist agent and 9 local tools
    ├── ticket.py              # GitHub Issues MCP specialist agent
    └── knowledge.py           # Azure AI Search specialist agent
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

### Create a virtual environment

```bash
# Set the base directory for virtual environments (add to your shell profile)
export HOME_VENVS=~/venvs  # or any directory you prefer

# Create and activate the venv
python3 -m venv $HOME_VENVS/specialistmesh
source $HOME_VENVS/specialistmesh/bin/activate
```

### Install and run

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Run the default hosted group chat workflow
python main.py
```

The hosted response server starts, initializes all specialists, and exposes the Responses protocol endpoint on port 8088.

### Runtime entry point

`main.py` is the current application entry point. Older experimental `main_*` variants have been removed, so local runs and hosted deployment both use the group chat workflow defined in `main.py`.

## Deployment

Deploy as a hosted agent in Azure AI Foundry:

```bash
# From the project root
azd ai agent create
```

### What Happens

1. **agent.yaml** defines the agent configuration (name, model, system prompt, tools).
2. **agent.manifest.yaml** provides metadata for the Foundry hosting.
3. **Dockerfile** packages the application in a Python 3.12 container and exposes port 8088.
4. Foundry handles routing of requests to the Response API and automatic scaling.

For more details on Foundry deployment, see the [Azure AI Foundry documentation](https://learn.microsoft.com/en-us/azure/ai-foundry/).

## Observability

The default group chat entry point creates custom spans around specialist execution through `agent_framework.observability.get_tracer()`. Those spans set agent attributes such as `gen_ai.agent.name`, `gen_ai.agent.id`, and `agent.name`, which makes specialist activity easier to distinguish in traces.

The Agent Framework and hosting runtime can emit OpenTelemetry data according to the environment and hosting configuration. Traces can include:

- **Agent invocations**: Start/end times, input/output, status
- **Tool calls**: Tool name, parameters, results, duration
- **Group chat routing**: Orchestrator selections and specialist/coordinator turns
- **Errors**: Full stack traces and context

View traces in the Azure Portal under your Application Insights resource, or via the Foundry project dashboard.

## References

- [Microsoft Agent Framework (Python)](https://github.com/microsoft/agent-framework/tree/main/python)
- [GitHub MCP Server](https://github.com/github/github-mcp-server)
- [Azure AI Search Documentation](https://learn.microsoft.com/en-us/azure/search/)
- [Azure AI Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry/)
- [OpenTelemetry Python](https://opentelemetry.io/docs/instrumentation/python/)
