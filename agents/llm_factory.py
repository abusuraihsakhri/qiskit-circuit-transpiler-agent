"""
Deterministic local mock with sensitive-identifier pattern screening.
"""
from typing import Dict, Any, Optional
from .base import PHIGuard


class MockLLM:
    def __init__(self, system_name: str = "Qiskit Circuit Transpiler Agent"):
        self.system_name = system_name

    def invoke(self, prompt: str) -> str:
        PHIGuard.assert_no_phi(prompt)
        return (
            "Deterministic demo only: no language model is connected. "
            "Use the audit endpoints for numerical threshold evaluations."
        )


class LLMFactory:
    """Creates configured LLM client instances with zero-PHI protection."""

    @staticmethod
    def create(provider: str = "mock", system_name: str = "Qiskit Circuit Transpiler Agent"):
        prov = str(provider).lower()
        if prov in {"mock", "deterministic", "test"}:
            return MockLLM(system_name)
        raise ValueError(
            f"Provider {provider!r} is not implemented; "
            "only the deterministic mock is available"
        )
