"""
config/settings.py

Central configuration for the IRIS application.
All magic numbers and tunable values live here.
Import specific constants — never import * from this module.
"""

# ── Identity ──────────────────────────────────────────────────────────────────
ASSISTANT_NAME: str = "IRIS"

# ── LLM ───────────────────────────────────────────────────────────────────────
DEFAULT_MODEL: str = "llama3.2"
LLM_TIMEOUT: int = 30              # Seconds before an LLM request is considered failed
LLM_TEMPERATURE: float = 0.7       # Response creativity (0.0 = deterministic, 1.0 = creative)
MAX_TOKENS: int = 2048             # Maximum tokens per LLM response

# ── Memory ────────────────────────────────────────────────────────────────────
MEMORY_DIR: str = "memory"
HISTORY_FILE: str = "memory/history.json"
METADATA_FILE: str = "memory/metadata.json"
SUMMARY_FILE: str = "memory/summary.json"
MAX_HISTORY: int = 15              # Recent turns kept in history storage
MAX_CONTEXT_HISTORY: int = 10      # Recent messages injected into each LLM prompt
MAX_CONTEXT_MEMORIES: int = 5      # Relevant memories injected into each prompt
CONTEXT_TOKEN_BUDGET: int = 3000   # Estimated max tokens for the assembled context
MAX_FILE_READ_CHARS: int = 5000    # Characters returned by FileReader before truncation

# ── Vector Store ──────────────────────────────────────────────────────────────
EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION: int = 384
VECTOR_INDEX_FILE: str = "memory/vector.index"   # FAISS binary index
VECTOR_META_FILE: str  = "memory/vector_meta.json"  # metadata for each vector
VECTOR_SEARCH_TOP_K: int = 3        # Number of similar memories to retrieve
SIMILARITY_THRESHOLD: float = 0.75  # Minimum similarity score to surface a memory

# ── Voice ─────────────────────────────────────────────────────────────────────
VOICE_SPEED: int = 175              # Words per minute for text-to-speech
AMBIENT_NOISE_DURATION: float = 1.0 # Seconds to sample ambient noise before listening

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_DIRECTORY: str = "logs"
LOG_FILE: str = "logs/iris.log"
LOG_MAX_BYTES: int = 5 * 1024 * 1024   # 5 MB per log file
LOG_BACKUP_COUNT: int = 3

# ── System Prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT: str = """
You are IRIS (Intelligent Reasoning Information System).

Your personality:
- Friendly and professional.
- Intelligent and logical.
- Answer accurately.
- If you don't know something, admit it.
- Keep answers concise unless asked for more detail.
- Address the user respectfully.
"""
