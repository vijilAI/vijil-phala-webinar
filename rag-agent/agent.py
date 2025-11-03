import os
import time
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from fastapi import FastAPI, Request
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph_openai_serve import LangchainOpenaiApiServe, GraphRegistry, GraphConfig
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Env (only here) ---
OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY")            # used if not using Redpill
REDPILL_API_KEY  = os.getenv("REDPILL_API_KEY")           # optional: use Redpill for chat if set
REDPILL_BASE_URL = os.getenv("REDPILL_BASE_URL")          # e.g. https://api.redpill.ai/v1
CHAT_MODEL       = os.getenv("CHAT_MODEL", "gpt-4o-mini")
TEMP             = float(os.getenv("RAG_TEMP", "0.2"))

# RAG tool
from tools import lookup_docs

# Custom callback handler for debugging LLM calls
class DebugCallbackHandler(BaseCallbackHandler):
    """Custom callback handler to log LLM interactions and errors."""
    
    def on_llm_start(self, serialized, prompts, **kwargs):
        """Log when LLM starts."""
        logger.info(f"🚀 LLM Start - Model: {serialized.get('name', 'unknown')}")
        logger.debug(f"   Prompts: {prompts}")
        if kwargs:
            logger.debug(f"   Kwargs: {kwargs}")
    
    def on_llm_end(self, response: LLMResult, **kwargs):
        """Log when LLM ends successfully."""
        logger.info(f"✅ LLM End - Generations: {len(response.generations)}")
        
    def on_llm_error(self, error: Exception, **kwargs):
        """Log when LLM encounters an error."""
        logger.error(f"❌ LLM Error: {type(error).__name__}")
        logger.error(f"   Error message: {str(error)}")
        logger.error(f"   Error details: {repr(error)}")
        if hasattr(error, 'response'):
            logger.error(f"   Response: {error.response}")
        if kwargs:
            logger.error(f"   Additional context: {kwargs}")

def _chat_llm():
    """Prefer Redpill if both vars are set; otherwise use OpenAI."""
    debug_handler = DebugCallbackHandler()
    
    if REDPILL_API_KEY and REDPILL_BASE_URL:
        logger.info(f"Using Redpill with model {CHAT_MODEL} at {REDPILL_BASE_URL}")
        return ChatOpenAI(
            model=CHAT_MODEL,
            api_key=REDPILL_API_KEY,
            base_url=REDPILL_BASE_URL,
            temperature=TEMP,
            max_tokens=300,  # Limit response length for faster generation
            timeout=30,  # 30 second timeout
            verbose=True,
            callbacks=[debug_handler]
        ).bind_tools([lookup_docs])
    else:
        logger.info(f"Using OpenAI with model: {CHAT_MODEL}")
        assert OPENAI_API_KEY, "OPENAI_API_KEY is required if not using Redpill."
        return ChatOpenAI(
            model=CHAT_MODEL,
            api_key=OPENAI_API_KEY,
            temperature=TEMP,
            max_tokens=300,  # Limit response length for faster generation
            timeout=30,  # 30 second timeout
            verbose=True,
            callbacks=[debug_handler]
        ).bind_tools([lookup_docs])

SYS_PROMPT = (
    "You are a Vijil documentation expert assistant. Your role is to provide accurate, "
    "concise answers based on the Vijil documentation.\n\n"
    "INSTRUCTIONS:\n"
    "1. Use the `lookup_docs` tool ONCE to search the documentation, then answer based on those results.\n"
    "2. DO NOT call lookup_docs multiple times for the same question.\n"
    "3. Base your answers strictly on the retrieved documentation snippets.\n"
    "4. When citing information, reference the source file when relevant.\n"
    "5. If the documentation doesn't contain the answer, acknowledge this clearly and briefly.\n"
    "6. Keep responses concise and technically accurate (2-3 sentences max when possible).\n"
)

# Build ReAct agent (this returns a compiled LangGraph)
react_agent_graph = create_react_agent(
    _chat_llm(),
    tools=[lookup_docs],
    prompt=SYS_PROMPT
)

# Serve it as a true OpenAI-compatible /v1/chat/completions endpoint
app = FastAPI(title="Vijil Docs Agent")

# Log startup configuration
logger.info("=" * 60)
logger.info("🚀 Vijil Docs Agent Starting")
logger.info("=" * 60)
logger.info(f"   Backend: {'Redpill' if REDPILL_API_KEY and REDPILL_BASE_URL else 'OpenAI'}")
if REDPILL_API_KEY and REDPILL_BASE_URL:
    logger.info(f"   Redpill URL: {REDPILL_BASE_URL}")
logger.info(f"   Model: {CHAT_MODEL}")
logger.info(f"   Temperature: {TEMP}")
logger.info("=" * 60)

# Add timing and error logging middleware
@app.middleware("http")
async def add_timing_and_error_logging(request: Request, call_next):
    start_time = time.time()
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(f"⏱️  Request completed in {process_time:.2f}s: {request.method} {request.url.path}")
        response.headers["X-Process-Time"] = str(process_time)
        return response
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"❌ Request failed after {process_time:.2f}s: {request.method} {request.url.path}")
        logger.error(f"   Exception type: {type(e).__name__}")
        logger.error(f"   Exception message: {str(e)}")
        logger.exception("Full traceback:")
        raise

registry = GraphRegistry(
    registry={
        # Clients will pass model="vijil-docs-agent" when calling /v1/chat/completions
        "vijil-docs-agent": GraphConfig(
            graph=react_agent_graph,
            streamable_node_names=["agent", "tools"]
        )
    }
)
LangchainOpenaiApiServe(app=app, graphs=registry).bind_openai_chat_completion(prefix="/v1")

# Run:
# uvicorn agent:app --host 0.0.0.0 --port 8000 --reload
