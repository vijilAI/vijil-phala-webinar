import os
import time
from langchain_core.tools import tool
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

# --- Env / tunables ---
DATA_ROOT   = os.getenv("RAG_DATA_DIR", "data/docs")
INDEX_DIR   = os.getenv("RAG_INDEX_DIR", "data/faiss_index")
OPENAI_KEY  = os.environ["OPENAI_API_KEY"]
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
CHUNK_SIZE  = int(os.getenv("RAG_CHUNK_SIZE", "800"))  # Reduced from 1200 for faster processing
CHUNK_OVERL = int(os.getenv("RAG_CHUNK_OVERLAP", "100"))  # Reduced from 200
TOP_K       = int(os.getenv("RAG_TOP_K", "3"))  # Reduced from 5 for faster responses

def _build_or_load_retriever():
    os.makedirs(INDEX_DIR, exist_ok=True)
    embeddings = OpenAIEmbeddings(
        api_key=OPENAI_KEY,
        model=EMBED_MODEL,
        chunk_size=100
    )

    # Try loading existing FAISS first (fast boot)
    try:
        vs = FAISS.load_local(INDEX_DIR, embeddings, allow_dangerous_deserialization=True)
        print(f"✓ Loaded existing FAISS index from {INDEX_DIR}")
        return vs.as_retriever(search_kwargs={"k": TOP_K})
    except Exception:
        pass

    # Build fresh from Markdown
    print(f"Building new FAISS index from {DATA_ROOT}...")
    loader = DirectoryLoader(
        DATA_ROOT,
        glob="**/*.md",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
        use_multithreading=True,
        silent_errors=True,
    )
    docs = loader.load()
    print(f"Loaded {len(docs)} documents")
    
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERL)
    chunks = splitter.split_documents(docs)
    print(f"Split into {len(chunks)} chunks, building index...")
    
    vs = FAISS.from_documents(chunks, embeddings)
    vs.save_local(INDEX_DIR)
    print(f"✓ FAISS index saved to {INDEX_DIR}")
    return vs.as_retriever(search_kwargs={"k": TOP_K})

_retriever = _build_or_load_retriever()

@tool
async def lookup_docs(query: str) -> str:
    """Search local Markdown (data/**/*.md) and return top snippets with sources."""
    start_time = time.time()
    print(f"🔍 Searching for: '{query[:50]}...'")
    
    # Use async ainvoke method for non-blocking retrieval
    docs = await _retriever.ainvoke(query)
    
    elapsed = time.time() - start_time
    print(f"⏱️  Retrieval took {elapsed:.2f}s (embedding + FAISS search)")
    
    result = "\n\n---\n".join(f"[{d.metadata.get('source','?')}]\n{d.page_content[:500]}..." 
                               if len(d.page_content) > 500 else f"[{d.metadata.get('source','?')}]\n{d.page_content}" 
                               for d in docs)
    print(f"⏱️  Returning {len(result)} chars from {len(docs)} docs")
    return result
