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
OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY")            # used if not using Groq, also for embeddings
GROQ_API_KEY  = os.getenv("GROQ_API_KEY")           # optional: use Groq for chat if set
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL")          # e.g. https://api.groq.com/v1
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
        """Log when LLM ends successfully and check for issues."""
        logger.info(f"✅ LLM End - Generations: {len(response.generations)}")
        
        # Check for empty responses and truncation
        has_content = False
        has_tool_calls = False
        has_invalid_tool_calls = False
        
        for gen_list in response.generations:
            for gen in gen_list:
                # Check for truncation
                if hasattr(gen, 'generation_info') and gen.generation_info:
                    finish_reason = gen.generation_info.get('finish_reason')
                    if finish_reason == 'length':
                        logger.warning("⚠️  Response truncated - consider increasing max_tokens")
                
                # Check if response has text content
                if hasattr(gen, 'text') and gen.text.strip():
                    has_content = True
                elif hasattr(gen, 'message'):
                    if gen.message.content and str(gen.message.content).strip():
                        has_content = True
                    
                    # Check for valid tool calls
                    if hasattr(gen.message, 'tool_calls') and gen.message.tool_calls:
                        has_tool_calls = True
                        logger.info(f"✅ Valid tool call: {gen.message.tool_calls[0].get('name')} with {len(str(gen.message.tool_calls[0]))} chars")
                    elif hasattr(gen.message, 'additional_kwargs'):
                        if gen.message.additional_kwargs.get('tool_calls'):
                            has_tool_calls = True
                            logger.info(f"✅ Valid tool call in additional_kwargs")
                    
                    # Check for invalid tool calls
                    if hasattr(gen.message, 'invalid_tool_calls') and gen.message.invalid_tool_calls:
                        has_invalid_tool_calls = True
                        invalid = gen.message.invalid_tool_calls[0]
                        logger.error(f"⚠️  INVALID TOOL CALL:")
                        logger.error(f"   Tool: {invalid.get('name')}")
                        logger.error(f"   Args (truncated?): {invalid.get('args')}")
                        logger.error(f"   Error: {invalid.get('error')}")
                        logger.error(f"   Completion tokens: {response.llm_output.get('token_usage', {}).get('completion_tokens', 'unknown')}")
                        logger.error(f"   This suggests the response was cut off mid-generation!")
        
        # Only error if there's no content AND no tool calls (valid or invalid)
        if not has_content and not has_tool_calls and not has_invalid_tool_calls:
            # Detailed debugging for empty responses
            for gen_list in response.generations:
                for gen in gen_list:
                    if hasattr(gen, 'message'):
                        logger.error("❌ EMPTY RESPONSE DEBUG:")
                        logger.error(f"   Content: '{gen.message.content}'")
                        logger.error(f"   Content type: {type(gen.message.content)}")
                        logger.error(f"   Additional kwargs: {gen.message.additional_kwargs}")
                        logger.error(f"   Tool calls attr exists: {hasattr(gen.message, 'tool_calls')}")
                        if hasattr(gen.message, 'tool_calls'):
                            logger.error(f"   Tool calls value: {gen.message.tool_calls}")
                        logger.error(f"   Invalid tool calls attr exists: {hasattr(gen.message, 'invalid_tool_calls')}")
                        if hasattr(gen.message, 'invalid_tool_calls'):
                            logger.error(f"   Invalid tool calls value: {gen.message.invalid_tool_calls}")
                        logger.error(f"   Response metadata: {gen.message.response_metadata}")
            logger.error(f"   Token usage: {response.llm_output.get('token_usage')}")
        elif (has_tool_calls or has_invalid_tool_calls) and not has_content:
            logger.debug(f"🔧 LLM made tool calls (content empty is expected)")
        
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
    """Prefer Groq if both vars are set; otherwise use OpenAI."""
    debug_handler = DebugCallbackHandler()
    
    if GROQ_API_KEY and GROQ_BASE_URL:
        logger.info(f"Using Groq with model {CHAT_MODEL} at {GROQ_BASE_URL}")
        return ChatOpenAI(
            model=CHAT_MODEL,
            api_key=GROQ_API_KEY,
            base_url=GROQ_BASE_URL,
            temperature=TEMP,
            max_tokens=2000,              # Increased - tool calls need overhead
            max_completion_tokens=3000,   # For reasoning models
            max_retries=2,
            timeout=100,
            verbose=True,
            callbacks=[debug_handler]
        ).bind_tools([lookup_docs])
    else:
        logger.info(f"Using OpenAI with model: {CHAT_MODEL}")
        assert OPENAI_API_KEY, "OPENAI_API_KEY is required if not using Groq."
        return ChatOpenAI(
            model=CHAT_MODEL,
            api_key=OPENAI_API_KEY,
            temperature=TEMP,
            max_tokens=2000,              # Increased - tool calls need overhead
            max_completion_tokens=3000,   # For reasoning models
            max_retries=2,
            timeout=100,
            verbose=True,
            callbacks=[debug_handler]
        ).bind_tools([lookup_docs])

SYS_PROMPT = (
    "You are a Vijil documentation expert assistant and general chatbot. Your role is to provide helpful "
    "answers about the Vijil documentation and general topics.\n\n"
    "INSTRUCTIONS:\n"
    "1. Use the `lookup_docs` tool to search the documentation.\n"
    "2. After using the tool, ALWAYS provide a text response summarizing what you found.\n"
    "3. CRITICAL: You MUST end with a text message to the user. Tool calls alone are not sufficient.\n"
    "4. If the tool returns no results: Say you couldn't find information and suggest alternatives.\n"
    "5. Keep responses concise but informative.\n"
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
logger.info(f"   Backend: {'Groq' if GROQ_API_KEY and GROQ_BASE_URL else 'OpenAI'}")
if GROQ_API_KEY and GROQ_BASE_URL:
    logger.info(f"   Groq URL: {GROQ_BASE_URL}")
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
