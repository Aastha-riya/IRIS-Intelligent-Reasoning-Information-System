"""
brain/llm.py

Wrapper around the Ollama LLM.
Delegates prompt assembly to MemoryManager.build_context() — the full
RAG pipeline runs there. LLM just calls Ollama and returns the reply.

Flow:
    user query
        ↓
    memory_manager.build_context()
        → retrieve_memory()  (semantic search)
        → load_history()     (recent turns)
        → context_builder.build()
        ↓
    ollama.chat(messages)
        ↓
    memory_manager.save_conversation()
        ↓
    reply string
"""

import ollama

from config.settings import DEFAULT_MODEL
from memory.memory_manager import MemoryManager
from utils.logger import logger


class LLM:
    """Sends prompts to the local Ollama model and returns responses."""

    def __init__(self, memory_manager: MemoryManager) -> None:
        self.memory_manager = memory_manager
        logger.debug(f"LLM initialized — model: {DEFAULT_MODEL}")

    def chat(self, prompt: str) -> str:
        """
        Send a user prompt through the full RAG pipeline and return the reply.

        The complete message list is assembled by MemoryManager.build_context(),
        which injects the system prompt, relevant memories, and recent history.
        """
        logger.info("Sending prompt to LLM...")

        # Full RAG context: system + memories + history + current prompt
        messages = self.memory_manager.build_context(prompt)

        try:
            response = ollama.chat(
                model=DEFAULT_MODEL,
                messages=messages,
            )
            reply: str = response["message"]["content"]

            # Persist exchange — also embeds into vector store
            self.memory_manager.save_conversation(prompt, reply)

            logger.info("Response received successfully.")
            return reply

        except Exception as e:
            logger.exception(f"LLM request failed: {e}")
            return "I encountered an error generating a response."
