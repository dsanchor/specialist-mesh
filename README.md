# Specialist Mesh

A multi-agent orchestration system built with Microsoft Agent Framework (Python) where a group chat orchestrator answers general requests directly or routes domain requests to specialized Foundry agents.

## Architecture

Specialist Mesh implements an **Orchestrator + 4 Specialists** pattern. The orchestrator answers greetings and general capability questions directly; domain requests are routed to one specialist, whose response is returned to the user.

```
┌─────────────────────────────────────────────────┐
│        User Request (Natural Language)          │
└─────────────────────────┬───────────────────────┘
                          │
                    ┌─────▼──────┐
                    │Orchestrator│ (Intent Detection & Speaker Selection)
                    └─────┬──────┘
       ┌────────────┬─────┴──────┬──────────────┐
       │            │            │              │
   ┌───▼────┐  ┌────▼───┐  ┌────▼───┐  ┌───────▼──┐
   │Billing │  │  IAM   │  │Ticket  │  │Knowledge │
   │ Agent  │  │ Agent  │  │ Agent  │  │ Agent    │
   │Foundry │  │Foundry │  │Foundry │  │ Foundry  │
   └────────┘  └────────┘  └────────┘  └──────────┘
```

### Agents

- **Orchestrator**: Answers general requests directly, or selects the appropriate specialist for domain work.
- **Billing Agent**: Existing Foundry agent named by `BILLING_AGENT_NAME`.
- **IAM Agent**: Existing Foundry agent named by `IAM_AGENT_NAME`.
- **Ticket Agent**: Existing Foundry agent named by `TICKETING_AGENT_NAME`.
- **Knowledge Agent**: Existing Foundry agent named by `KNOWLEDGE_BASE_AGENT_NAME`.

## Key Features

- **Single-turn GroupChat Orchestration**: The default entry point uses a group chat workflow where the orchestrator answers general requests directly, or chooses one specialist whose response is returned to the user without a final orchestration message.
- **Hosted Agent Deployment**: Deploy as a response API in Azure AI Foundry with streamlined containerization.
- **Foundry Specialist Agents**: Billing, IAM, Ticketing, and Knowledge Base specialists are connected as existing Foundry agents.

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
    ├── billing.py             # Legacy local Billing specialist implementation
    ├── iam.py                 # Legacy local IAM specialist implementation
    ├── ticket.py              # Legacy local Ticket specialist implementation
    └── knowledge.py           # Legacy local Knowledge specialist implementation
```

## Prerequisites

- **Python 3.12+**
- **Azure AI Foundry Project** with Azure Application Insights enabled
- **Existing Foundry agents** for Billing, IAM, Ticketing, and Knowledge Base
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
| `BILLING_AGENT_NAME` | Existing Billing specialist agent name in Foundry | `BillingAgent` |
| `BILLING_AGENT_VERSION` | Billing specialist agent version | `3` |
| `IAM_AGENT_NAME` | Existing IAM specialist agent name in Foundry | `IAMAgent` |
| `IAM_AGENT_VERSION` | IAM specialist agent version | `4` |
| `TICKETING_AGENT_NAME` | Existing Ticketing specialist agent name in Foundry | `TitketingAgent` |
| `TICKETING_AGENT_VERSION` | Ticketing specialist agent version | `3` |
| `KNOWLEDGE_BASE_AGENT_NAME` | Existing Knowledge Base specialist agent name in Foundry | `KnowledgeBaseAgent` |
| `KNOWLEDGE_BASE_AGENT_VERSION` | Knowledge Base specialist agent version | `3` |
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

The Agent Framework and hosting runtime can emit OpenTelemetry data according to the environment and hosting configuration. Traces can include:

- **Agent invocations**: Start/end times, input/output, status
- **Tool calls**: Tool name, parameters, results, duration
- **Group chat routing**: Orchestrator selections and specialist turns
- **Errors**: Full stack traces and context

View traces in the Azure Portal under your Application Insights resource, or via the Foundry project dashboard.

## References

- [Microsoft Agent Framework (Python)](https://github.com/microsoft/agent-framework/tree/main/python)
- [GitHub MCP Server](https://github.com/github/github-mcp-server)
- [Azure AI Search Documentation](https://learn.microsoft.com/en-us/azure/search/)
- [Azure AI Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry/)
- [OpenTelemetry Python](https://opentelemetry.io/docs/instrumentation/python/)
