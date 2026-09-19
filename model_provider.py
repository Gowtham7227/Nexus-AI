"""
NexusAI - Model Provider Layer
Unified abstraction for Gemini (Cloud) and Qwen (Local Ollama) models
with built-in Output Privacy Guarding and injection protection.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Generator

from privacy_scanner import OutputPrivacyGuard, PromptInjectionShield
from chatbot import ask_gemini, ask_gemini_general
from local_llm import ask_local, stream_local


class BaseModelProvider(ABC):
    """Abstract interface for LLM execution with security boundaries."""

    @abstractmethod
    def generate_response(
        self,
        context: Optional[str],
        question: str,
        user_id: Optional[str] = None
    ) -> str:
        """Generate response given context and user question."""
        pass


class GeminiModelProvider(BaseModelProvider):
    """Google Gemini Cloud LLM Provider."""

    def __init__(self):
        self.shield = PromptInjectionShield()
        self.output_guard = OutputPrivacyGuard()

    def generate_response(
        self,
        context: Optional[str],
        question: str,
        user_id: Optional[str] = None
    ) -> str:
        if context and context.strip():
            # Apply prompt injection defense if context is present
            wrapped_context = self.shield.isolate_context(context)
            raw_output = ask_gemini(wrapped_context, question)
        else:
            raw_output = ask_gemini_general(question)

        # Apply output privacy guard
        clean_output, redacted = self.output_guard.guard_output(raw_output, user_id=user_id)
        return clean_output


class LocalQwenModelProvider(BaseModelProvider):
    """Local Qwen / Ollama Model Provider."""

    def __init__(self):
        self.shield = PromptInjectionShield()
        self.output_guard = OutputPrivacyGuard()

    def generate_response(
        self,
        context: Optional[str],
        question: str,
        user_id: Optional[str] = None
    ) -> str:
        if context and context.strip():
            wrapped_context = self.shield.isolate_context(context)
            raw_output = ask_local(wrapped_context, question)
        else:
            raw_output = ask_local("", question)

        clean_output, redacted = self.output_guard.guard_output(raw_output, user_id=user_id)
        return clean_output


def get_model_provider(mode: str = "gemini") -> BaseModelProvider:
    """Factory for model providers."""
    if mode == "local":
        return LocalQwenModelProvider()
    return GeminiModelProvider()
