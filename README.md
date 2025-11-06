# Vijil × Phala Webinar: RAG Agent with Guardrails

This repository is for the **Vijil × Phala webinar**, demonstrating how to:
1. **Deploy** an AI agent on Phala Network
2. **Test** it using Vijil Evaluate to find vulnerabilities
3. **Fix** it by applying recommended Vijil Dome guardrails
4. **Redeploy** the secured agent back to Phala

The complete workflow shows how to move from an unguarded agent to a production-ready, secured agent using data-driven guardrails.

## 🎯 Quick Reference

| Component | Model/Provider | Purpose |
|-----------|----------------|---------|
| **Chat LLM** | `qwen/qwen3-32b` on Groq | Agent reasoning and responses |
| **Embeddings** | OpenAI `text-embedding-3-small` | RAG document retrieval |
| **Base Agent** | `rag-agent/` | For evaluation (no guardrails) |
| **Base Agent (Docker)** | `public.ecr.aws/h6q2v0i0/vijil-docs-agent:0.0.18` | Pre-built image for deployment |
| **Production Agent** | `rag-agent-guardrailed/` | With recommended guardrails (uses CPU-only PyTorch) |
| **Production Agent (Docker)** | `public.ecr.aws/h6q2v0i0/vijil-docs-agent-guardrailed:0.0.11` | Pre-built image for deployment |
| **Evaluation** | `evaluate-connection.ipynb` | Run tests, get recommendations |

> 🔑 **Key Setup:** OpenAI API key is **required** (for embeddings), Groq API key is **recommended** (for chat).  
> 🐳 **Deploy on Phala:** Just upload `compose.yaml` + `.env` - that's it!

---

## 🔄 The Webinar Workflow

1. **Deploy** base agent to Phala (`rag-agent/`) - no guardrails, ready for testing
2. **Test** using Vijil Evaluate to identify vulnerabilities and security issues
3. **Get** recommended guardrail configuration from evaluation results
4. **Fix** by applying recommended guardrails (`rag-agent-guardrailed/`)
5. **Redeploy** secured agent to Phala - now production-ready with data-driven protection

The `rag-agent-guardrailed` uses the **exact guardrail configuration recommended by Vijil Evaluate** after analyzing the base agent's security, safety, and privacy risks discovered during testing.

## 📁 Repository Structure

```
vijil-phala-webinar/
├── rag-agent/                    # 1️⃣ Base agent (deploy to Phala for testing)
│   ├── agent.py                  # Main agent implementation
│   ├── tools.py                  # RAG lookup tool
│   ├── requirements.txt          # Python dependencies
│   └── docker/
│       └── compose.yaml          # Phala deployment config
│
├── evaluate-connection.ipynb     # 2️⃣ Test agent & get guardrail recommendations
│
└── rag-agent-guardrailed/        # 3️⃣ Secured agent (redeploy to Phala for production)
    ├── agent.py                  # Guarded agent (applies recommended config)
    ├── tools.py                  # RAG lookup tool
    ├── requirements.txt          # Python dependencies (includes vijil_dome)
    └── docker/
        └── compose.yaml          # Phala deployment config (with guardrails)
```

> **Webinar Flow:** Deploy → Test → Fix → Redeploy  
> **Phala Deployment:** Just upload `compose.yaml` + `.env` - no build required!

---

## 🤖 The Agents

Both agents are **Vijil documentation assistants** that use RAG (Retrieval-Augmented Generation) to answer questions about Vijil's platform. They expose an OpenAI-compatible `/v1/chat/completions` endpoint built with:

- **LangGraph** - Agent orchestration framework
- **LangChain** - LLM integration (OpenAI/Groq)
- **FastAPI** - REST API server
- **ChromaDB** - Vector database for document retrieval

### Model Configuration

**Default Model:** `qwen/qwen3-32b` via Groq

**Supported Providers:**
- **Groq** (recommended for this demo)
- **OpenAI**

> ⚠️ **Important:** OpenAI API key is **required for embeddings** even when using Groq for chat completion.

### 1. `rag-agent/` - Base Agent (For Evaluation)

**Purpose:** Clean, unguarded agent designed for evaluation by Vijil Evaluate platform.

**Features:**
- OpenAI or Groq LLM backend support
- RAG tool for documentation lookup
- Comprehensive debug logging
- OpenAI-compatible API endpoint

**Use Cases:**
- Baseline evaluation with Vijil Evaluate
- Performance benchmarking
- Testing agent behavior without guardrails

### 2. `rag-agent-guardrailed/` - Production Agent (With Recommended Guardrails)

**Purpose:** Production-ready agent using **guardrails recommended by Vijil Evaluate** after analyzing the base agent.

**Features:**
- All features from base agent
- **Input Guardrails** *(recommended by evaluation)*:
  - Prompt injection detection (mBERT)
  - Content moderation (Flashtext)
  - PII detection (Presidio)
- **Output Guardrails** *(recommended by evaluation)*:
  - Toxicity detection (DeBERTa)
  - Content moderation (Flashtext)
- Async guardrail execution with proper thread pooling
- Request sanitization and blocking

> **Note:** The guardrail configuration is generated from Step 7 of the evaluation workflow (see `evaluate-connection.ipynb`).

**Use Cases:**
- Production deployment with data-driven security
- High-security environments
- Compliance requirements (PII/toxicity filtering)

---

## 🚀 Quick Start

### Deployment Options

**Option 1: Docker (Recommended for Phala)** - See [Docker Deployment](#-docker--phala-deployment)  
**Option 2: Local Development** - See instructions below

### Prerequisites

- Python 3.11+ (for local development)
- Docker (for containerized deployment)
- **API Keys & Credentials:**
  - **For Agent Deployment:** OpenAI API Key (embeddings) + Groq API Key (chat) or just OpenAI for both
  - **For Evaluation Notebook:** Vijil Platform Credentials (client ID, secret, token)

### 1. Setup Base Agent

```bash
cd rag-agent
pip install -r requirements.txt

# Create .env file with Groq (recommended for this demo)
cat > .env << EOF
# OpenAI key (REQUIRED for embeddings)
OPENAI_API_KEY=sk-...

# Groq configuration (for chat completion)
GROQ_API_KEY=gsk_...
GROQ_BASE_URL=https://api.groq.com/openai/v1
CHAT_MODEL=qwen/qwen3-32b

# Agent configuration
RAG_TEMP=0.2
EOF

# Run the agent
uvicorn agent:app --host 0.0.0.0 --port 8000
```

**Alternative: Use OpenAI for everything**
```bash
cat > .env << EOF
# OpenAI only (for both embeddings and chat)
OPENAI_API_KEY=sk-...
CHAT_MODEL=gpt-4o-mini
RAG_TEMP=0.2
EOF
```

> 💡 **How it works:** The agent automatically uses Groq for chat if both `GROQ_API_KEY` and `GROQ_BASE_URL` are set. Otherwise, it defaults to OpenAI. Embeddings always use OpenAI.

### 2. Setup Guardrailed Agent

```bash
cd rag-agent-guardrailed
pip install -r requirements.txt

# Copy .env from base agent
cp ../rag-agent/.env .

# Run the guardrailed agent
uvicorn agent:app --host 0.0.0.0 --port 8000
```

**💡 CPU-Only PyTorch Setup:**

For local development, install CPU-only PyTorch (~100-200MB) **before** installing requirements to avoid downloading CUDA PyTorch (~2-3GB):

```bash
cd rag-agent-guardrailed

# Install CPU-only PyTorch first
pip install torch --index-url https://download.pytorch.org/whl/cpu

# Then install remaining dependencies
pip install -r requirements.txt

# Run the agent
uvicorn agent:app --host 0.0.0.0 --port 8000
```

**Why this order?** Installing `torch` first ensures `vijil-dome` uses the existing CPU-only version instead of trying to install CUDA PyTorch.

> 🐳 **Docker users:** The Dockerfile already handles this automatically - no manual steps needed!

**Performance:** All guardrails remain fully functional on CPU. Model inference will be 2-5x slower than GPU, but for most guardrailing use cases, CPU performance is acceptable.

### 3. Test the Agent

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "vijil-docs-agent",
    "messages": [
      {"role": "user", "content": "What is Vijil Dome?"}
    ]
  }'
```

**Expected Startup Logs:**
```
🚀 Vijil Docs Agent Starting
================================================
   Backend: Groq
   Groq URL: https://api.groq.com/openai/v1
   Model: qwen/qwen3-32b
   Temperature: 0.2
================================================
```

> ✅ Verify "Backend: Groq" and model is `qwen/qwen3-32b` for this demo.

---

## 🐳 Docker & Phala Deployment

Both agents are available as **pre-built Docker images** hosted on AWS ECR (public repository). You can deploy them anywhere Docker is supported, including **Phala Network**.

### Available Docker Images

| Agent | Docker Image | Description |
|-------|-------------|-------------|
| **Base Agent** | `public.ecr.aws/h6q2v0i0/vijil-docs-agent:0.0.18` | For evaluation (no guardrails) |
| **Guardrailed Agent** | `public.ecr.aws/h6q2v0i0/vijil-docs-agent-guardrailed:0.0.11` | Production with recommended guardrails |

> 🌐 **Public Images:** No authentication required - pull and deploy directly!

### Deploying on Phala Network

**Deployment is incredibly simple - you only need 2 files:**

1. **`compose.yaml`** - Points to the pre-built Docker image (already in the repo)
2. **`.env`** - Your API keys and configuration

**No code changes. No build steps. No Docker registry setup. Just upload and go!** 🎉

The Docker images are hosted on AWS ECR (public) and automatically pulled by Phala.

#### Step 1: Prepare Your Environment File

**For Base Agent (`rag-agent/.env`):**
```bash
# Required
OPENAI_API_KEY=sk-...
GROQ_API_KEY=gsk_...
GROQ_BASE_URL=https://api.groq.com/openai/v1
CHAT_MODEL=qwen/qwen3-32b

# Optional (these have defaults)
RAG_TEMP=0.2
EMBED_MODEL=text-embedding-3-small
```

**For Guardrailed Agent (`rag-agent-guardrailed/.env`):**
```bash
# Same as base agent - guardrails are pre-configured in the image
OPENAI_API_KEY=sk-...
GROQ_API_KEY=gsk_...
GROQ_BASE_URL=https://api.groq.com/openai/v1
CHAT_MODEL=qwen/qwen3-32b
RAG_TEMP=0.2
```

#### Step 2: Deploy to Phala

Upload these files to Phala:
- `rag-agent/docker/compose.yaml` + `.env` → **Base agent** (for evaluation)
- `rag-agent-guardrailed/docker/compose.yaml` + `.env` → **Production agent** (with guardrails)

Phala will automatically:
1. Pull the Docker image from AWS ECR
2. Load your environment variables
3. Start the agent on port 8000
4. Provide you with a public URL

#### Step 3: Verify Deployment

Test your deployed agent:
```bash
curl https://your-phala-url.phala.network/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "vijil-docs-agent",
    "messages": [
      {"role": "user", "content": "What is Vijil?"}
    ]
  }'
```

Health check endpoint:
```bash
curl https://your-phala-url.phala.network/v1/health
```

### Local Docker Deployment

**Base Agent:**
```bash
cd rag-agent/docker
docker compose up -d
```

**Guardrailed Agent:**
```bash
cd rag-agent-guardrailed/docker
docker compose up -d
```

Both will be available at `http://localhost:8000/v1/chat/completions`

> 💡 **CPU-Only PyTorch:** The guardrailed agent's Dockerfile installs CPU-only PyTorch first (before other dependencies), preventing CUDA installation and reducing the Docker image size by ~2GB.

### Docker Image Details

The images include:
- ✅ Pre-indexed Vijil documentation (RAG data)
- ✅ All Python dependencies installed
- ✅ FastAPI server configured
- ✅ Health check endpoint (`/v1/health`)
- ✅ OpenAI-compatible API (`/v1/chat/completions`)
- ✅ Guardrails configured (guardrailed image only)
- ✅ **CPU-only PyTorch** (~100-200MB vs ~2-3GB with CUDA) - installed first in Dockerfile

> 📦 **Efficient Build:** The Dockerfile installs CPU-only PyTorch **before** installing dependencies, so `vijil-dome` uses it instead of downloading CUDA PyTorch. No double installation!

**Environment Variables Supported:**

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | **YES** | - | For embeddings |
| `GROQ_API_KEY` | **YES** | - | For chat completion |
| `GROQ_BASE_URL` | **YES** | - | Groq API endpoint |
| `CHAT_MODEL` | **YES** | - | Model name (e.g., `qwen/qwen3-32b`) |
| `RAG_TEMP` | No | `0.2` | LLM temperature |
| `EMBED_MODEL` | No | `text-embedding-3-small` | OpenAI embedding model |
| `RAG_TOP_K` | No | `5` | Number of RAG results |
| `RAG_CHUNK_SIZE` | No | `1200` | Document chunk size |
| `RAG_CHUNK_OVERLAP` | No | `200` | Chunk overlap |

---

## 📊 Evaluation Workflow

The `evaluate-connection.ipynb` notebook demonstrates the complete evaluation-to-production pipeline:

### Step-by-Step Process

1. **Authentication**
   - Swap M2M token for 24-hour access token
   - Login to Vijil platform

2. **API Key Registration**
   - Register agent endpoint (`rag-agent/`) with rate limits
   - Configure authentication

3. **Run Evaluation**
   - Select test harnesses (security, safety)
   - Configure model parameters
   - Initiate evaluation on base agent

4. **Monitor Progress**
   - Check evaluation status
   - Track completion

5. **Get Results**
   - Download PDF Trust Report
   - View detailed metrics and vulnerabilities found

6. **Generate Guardrail Config** ⭐
   - Fetch **recommended Dome configuration** based on evaluation results
   - This config identifies which guardrails to apply based on detected risks

7. **Apply to Production Agent**
   - The generated config is implemented in `rag-agent-guardrailed/agent.py`
   - Deploy with confidence knowing guardrails address real vulnerabilities

### Running the Notebook

```bash
# Install Jupyter
pip install jupyter

# Launch notebook
jupyter notebook evaluate-connection.ipynb
```

**Required Environment Variables:**

Add these to `rag-agent/.env` (the notebook loads from there):

```bash
# Vijil Platform Credentials
VIJIL_CLIENT_ID=your_client_id
VIJIL_CLIENT_SECRET=your_client_secret
VIJIL_CLIENT_TOKEN=your_client_token

# LLM Configuration (must match your deployed agent)
OPENAI_API_KEY=sk-...          # Required for embeddings
GROQ_API_KEY=gsk_...           # For chat completion
GROQ_BASE_URL=https://api.groq.com/openai/v1
CHAT_MODEL=qwen/qwen3-32b      # Model being evaluated
```

**Notebook Configuration:**

In Cell 13, update the agent URL to point to your deployed base agent:
```python
# Example: Phala deployment URL
agent_url = "https://88b5c6a7c5f2975e5851f311fba51dc995c0736f-8000.dstack-pha-prod7.phala.network/v1"

# Or local deployment
# agent_url = "http://localhost:8000/v1"

agent_model_name = "vijil-docs-agent"  # Model name from agent.py registry
```

> 💡 **Tip:** Deploy the base agent to Phala first, then use its public URL in the evaluation notebook.

---

## ⚙️ Environment Variables Reference

### Agent Configuration

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `OPENAI_API_KEY` | **YES** | OpenAI API key (used for embeddings in all cases) | `sk-proj-...` |
| `GROQ_API_KEY` | Optional | Groq API key for chat completion | `gsk_...` |
| `GROQ_BASE_URL` | Optional | Groq API base URL (must be set with GROQ_API_KEY) | `https://api.groq.com/openai/v1` |
| `CHAT_MODEL` | **YES** | Model name for chat completion | `qwen/qwen3-32b` (Groq) or `gpt-4o-mini` (OpenAI) |
| `RAG_TEMP` | Optional | Temperature for LLM responses | `0.2` (default) |

### Evaluation Configuration

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `VIJIL_CLIENT_ID` | **YES** | Vijil platform client ID | From Vijil dashboard |
| `VIJIL_CLIENT_SECRET` | **YES** | Vijil platform client secret | From Vijil dashboard |
| `VIJIL_CLIENT_TOKEN` | **YES** | Vijil platform M2M token | From Vijil dashboard |

### Provider Selection Logic

```python
if GROQ_API_KEY and GROQ_BASE_URL:
    # Use Groq for chat completion
    # Use OpenAI for embeddings (OPENAI_API_KEY required)
else:
    # Use OpenAI for both chat and embeddings
```

### Supported Models

**Groq (Recommended):**
- `qwen/qwen3-32b` (default for this demo)
- Other Groq models with tool calling support

**OpenAI:**
- `gpt-4o-mini`
- `gpt-4o`
- `gpt-4-turbo`
- `gpt-3.5-turbo`

> ⚠️ **Important:** Not all models support tool calling. Ensure your chosen model has OpenAI-style function calling capabilities.

---

## 🛡️ Guardrails Configuration

The `rag-agent-guardrailed` implements the **recommended Vijil Dome configuration** generated from the evaluation (notebook Cell 26).

### Recommended Configuration:

```python
guardrail_config = {
    'input-guards': ['security-input-guard', 'moderation-input-guard', 'privacy-input-guard'],
    'output-guards': ['moderation-output-guard'],
    'input-early-exit': True,
    
    'security-input-guard': {
        'type': 'security',
        'early-exit': True,
        'methods': ['prompt-injection-mbert']
    },
    'moderation-input-guard': {
        'type': 'moderation',
        'early-exit': True,
        'methods': ['moderation-flashtext']
    },
    'moderation-output-guard': {
        'type': 'moderation',
        'early-exit': True,
        'methods': ['moderation-deberta', 'moderation-flashtext']
    },
    'privacy-input-guard': {
        'type': 'privacy',
        'methods': ['privacy-presidio']
    }
}
```

### How This Config Was Generated

From `evaluate-connection.ipynb` (Cell 26):
```python
dome_config = get_config_from_vijil_evaluation(
    api_token=access_token,
    evaluation_id=eval_id
)
```

This returns the **exact configuration** shown above, tailored to the vulnerabilities found in the base agent.

**Key Features:**
- **Early Exit:** Stops processing immediately when threats are detected
- **Multi-Layer Protection:** Security, moderation, and privacy checks
- **Async Execution:** Non-blocking guardrail checks with thread pooling
- **Data-Driven:** Each guard addresses specific risks identified during evaluation

---

## 📚 Additional Resources

- [Vijil Documentation](https://docs.vijil.ai/)
- [Vijil Dome Config Guide](https://docs.vijil.ai/dome/config.html)

---

## 🤝 Support

For questions or issues:
- **Vijil Platform:** vele@vijil.ai
- **Technical Issues:** Open an issue in this repository

---

## 🙏 Acknowledgments

Built for the **Vijil × Phala Network Webinar** demonstrating agent evaluation and guardrails integration.

