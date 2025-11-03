import os
import time
import logging
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from fastapi import FastAPI, Request
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph_openai_serve import LangchainOpenaiApiServe, GraphRegistry, GraphConfig
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import MessagesState
from langchain_core.messages import HumanMessage, AIMessage
from typing import Dict, List
from dataclasses import dataclass

# Import Dome components for guardrails
from vijil_dome import Dome

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Env (only here) ---
OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY")            # used if not using Redpill
REDPILL_API_KEY  = os.getenv("REDPILL_API_KEY")           # optional: use Redpill for chat if set
REDPILL_BASE_URL = os.getenv("REDPILL_BASE_URL")          # e.g. https://api.redpill.ai/v1
CHAT_MODEL       = os.getenv("CHAT_MODEL", "gpt-4o-mini")
TEMP             = float(os.getenv("RAG_TEMP", "0.2"))
DOME_CONFIG_PATH = os.getenv("DOME_CONFIG_PATH")          # optional: path to Dome guardrail config JSON

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

def _initialize_dome():
    """Initialize Dome guardrails from config file or use defaults."""
    if DOME_CONFIG_PATH and os.path.exists(DOME_CONFIG_PATH):
        logger.info(f"Loading Dome config from: {DOME_CONFIG_PATH}")
        with open(DOME_CONFIG_PATH, 'r') as f:
            guardrail_config = json.load(f)
    else:
        logger.info("Using default Dome guardrail configuration")
        # Default configuration with security and moderation guards
        guardrail_config = {
            "input-guards": [{
                "security-scanner": {
                    "type": "security",
                    "methods": ['prompt-injection-deberta-v3-base'],
                }
            }],
            "output-guards": [{
                "content-filter": {
                    "type": "moderation",
                    "methods": ['moderation-flashtext'],
                }
            }],
        }
    
    # Initialize Dome
    dome = Dome(guardrail_config)
    logger.info("✅ Dome guardrails initialized successfully")
    return dome

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

# Initialize Dome guardrails
dome = _initialize_dome()

# Create wrapper state for guarded agent
@dataclass
class GuardedState(MessagesState):
    """State that extends MessagesState for guardrail wrapper."""
    pass

# Create async node that wraps react agent with guardrails
async def guarded_react_node(state: GuardedState):
    """
    Node that applies input guardrails, calls the react agent, and applies output guardrails.
    """
    msgs = state["messages"]
    
    # 1) INPUT GUARD - check the latest user message
    last_user = next((m for m in reversed(msgs) if isinstance(m, HumanMessage)), None)
    if last_user:
        logger.info(f"🛡️ Checking input guardrails for: {last_user.content[:50]}...")
        scan_in = await dome.async_guard_input(last_user.content)
        
        if getattr(scan_in, "flagged", False):
            logger.warning(f"⛔ Input blocked by guardrails")
            return {
                "messages": [AIMessage(content=getattr(
                    scan_in, 
                    "guardrail_response_message",
                    "I cannot process this request as it violates our security policies."
                ))]
            }
        
        # Apply sanitized input if guardrails modified it
        sanitized = getattr(scan_in, "guardrail_response_message", None)
        if sanitized and sanitized != last_user.content:
            logger.info(f"🔧 Input sanitized by guardrails")
            # Replace the last user message with sanitized version
            msgs = list(msgs[:-1]) + [HumanMessage(content=sanitized)]
    
    # 2) CALL THE REACT AGENT
    logger.info(f"🤖 Processing through react agent...")
    result = await react_agent_graph.ainvoke({"messages": msgs})
    ai_msg = next((m for m in reversed(result["messages"]) if isinstance(m, AIMessage)), None)
    
    if not ai_msg:
        logger.warning(f"⚠️ No assistant message in agent response")
        return {"messages": [AIMessage(content="No response generated.")]}
    
    # 3) OUTPUT GUARD - check the assistant reply
    logger.info(f"🛡️ Checking output guardrails...")
    scan_out = await dome.async_guard_output(ai_msg.content)
    
    if getattr(scan_out, "flagged", False):
        logger.warning(f"⛔ Output blocked by guardrails")
        final_text = "The generated response was blocked by our content filters."
    else:
        final_text = getattr(scan_out, "guardrail_response_message", ai_msg.content)
    
    logger.info(f"✅ Guardrails passed, returning response")
    return {"messages": [AIMessage(content=final_text)]}

# Create wrapper graph: START -> guarded_react_node -> END
logger.info("Building guarded agent graph wrapper...")
wrapper_graph = StateGraph(GuardedState)
wrapper_graph.add_node("react", guarded_react_node)
wrapper_graph.add_edge(START, "react")
wrapper_graph.add_edge("react", END)
guarded_agent_graph = wrapper_graph.compile()
logger.info("✅ Guarded agent graph compiled successfully")

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
logger.info(f"   Guardrails: {'Custom Config' if DOME_CONFIG_PATH else 'Default Config'}")
if DOME_CONFIG_PATH:
    logger.info(f"   Config Path: {DOME_CONFIG_PATH}")
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
        # The guarded_agent_graph wraps the react agent with Dome guardrails
        "vijil-docs-agent": GraphConfig(
            graph=guarded_agent_graph,
            streamable_node_names=["react"]  # Our wrapper has a single "react" node
        )
    }
)
LangchainOpenaiApiServe(app=app, graphs=registry).bind_openai_chat_completion(prefix="/v1")

# Run:
# uvicorn agent:app --host 0.0.0.0 --port 8000 --reload
