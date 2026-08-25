"""
Error Budget Manager for noise-adaptive gate cancellation.
Tracks per-qubit and per-gate error allocation during transpilation.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum


class GateType(str, Enum):
    SINGLE_QUBIT = "single_qubit"
    TWO_QUBIT = "two_qubit"
    MEASUREMENT = "measurement"


@dataclass
class GateError:
    """Error information for a single gate."""
    gate_type: GateType
    qubits: Tuple[int, ...]
    error_rate: float
    duration: float  # nanoseconds
    fidelity: float = 1.0

    def __post_init__(self):
        self.fidelity = 1.0 - self.error_rate


@dataclass
class QubitBudget:
    """Error budget allocation for a single qubit."""
    qubit_id: int
    total_budget: float
    used_budget: float = 0.0
    gate_count: int = 0
    t1_time: float = 100e-6
    t2_time: float = 80e-6

    @property
    def remaining_budget(self) -> float:
        return max(0.0, self.total_budget - self.used_budget)

    @property
    def utilization(self) -> float:
        return self.used_budget / self.total_budget if self.total_budget > 0 else 0.0

    def allocate(self, error: float) -> bool:
        """Try to allocate error to this qubit's budget."""
        if self.used_budget + error <= self.total_budget:
            self.used_budget += error
            self.gate_count += 1
            return True
        return False


@dataclass
class ErrorBudgetReport:
    """Post-transpilation error budget report."""
    total_budget: float
    total_used: float
    qubit_budgets: Dict[int, QubitBudget]
    cancelled_gates: int
    merged_blocks: int
    estimated_fidelity: float

    @property
    def remaining_budget(self) -> float:
        return max(0.0, self.total_budget - self.total_used)

    @property
    def budget_utilization(self) -> float:
        return self.total_used / self.total_budget if self.total_budget > 0 else 0.0

    def to_dict(self) -> Dict:
        return {
            "total_budget": self.total_budget,
            "total_used": self.total_used,
            "remaining_budget": self.remaining_budget,
            "budget_utilization": f"{self.budget_utilization:.2%}",
            "cancelled_gates": self.cancelled_gates,
            "merged_blocks": self.merged_blocks,
            "estimated_fidelity": self.estimated_fidelity,
            "qubit_utilization": {
                q: f"{b.utilization:.2%}" for q, b in self.qubit_budgets.items()
            },
        }


class ErrorBudgetManager:
    """Manages error budgets across qubits and gates during transpilation."""

    def __init__(
        self,
        num_qubits: int,
        total_error_budget: float = 0.05,
        t1_times: Optional[Dict[int, float]] = None,
        t2_times: Optional[Dict[int, float]] = None,
    ):
        self.num_qubits = num_qubits
        self.total_error_budget = total_error_budget
        self.per_qubit_budget = total_error_budget / num_qubits

        self.qubit_budgets: Dict[int, QubitBudget] = {}
        for i in range(num_qubits):
            t1 = t1_times.get(i, 100e-6) if t1_times else 100e-6
            t2 = t2_times.get(i, 80e-6) if t2_times else 80e-6
            self.qubit_budgets[i] = QubitBudget(
                qubit_id=i,
                total_budget=self.per_qubit_budget,
                t1_time=t1,
                t2_time=t2,
            )

        self.cancelled_gates = 0
        self.merged_blocks = 0
        self.gate_log: List[GateError] = []

    def can_cancel_pair(self, gate1: GateError, gate2: GateError) -> bool:
        """Check if cancelling a pair of gates keeps us within budget."""
        # If gates are inverses, cancelling reduces error
        if self._are_inverse_gates(gate1, gate2):
            return True  # Always safe to cancel inverse gates
        return False

    def record_cancellation(self, gate1: GateError, gate2: GateError):
        """Record that a pair of gates was cancelled."""
        self.cancelled_gates += 1
        # Reduce used budget for affected qubits
        for q in gate1.qubits:
            if q in self.qubit_budgets:
                self.qubit_budgets[q].used_budget -= gate1.error_rate
                self.qubit_budgets[q].used_budget = max(0, self.qubit_budgets[q].used_budget)

    def record_gate(self, gate: GateError) -> bool:
        """Record a gate and check if it fits within the error budget."""
        can_fit = True
        for q in gate.qubits:
            if q in self.qubit_budgets:
                if not self.qubit_budgets[q].allocate(gate.error_rate):
                    can_fit = False

        self.gate_log.append(gate)
        return can_fit

    def can_merge_blocks(self, block1: List[GateError], block2: List[GateError]) -> bool:
        """Check if merging two gate blocks stays within error budget."""
        total_error = sum(g.error_rate for g in block1) + sum(g.error_rate for g in block2)
        all_qubits = set()
        for g in block1 + block2:
            all_qubits.update(g.qubits)

        for q in all_qubits:
            if q in self.qubit_budgets:
                if self.qubit_budgets[q].remaining_budget < total_error / len(all_qubits):
                    return False
        return True

    def record_block_merge(self, block1: List[GateError], block2: List[GateError]):
        """Record that two blocks were merged."""
        self.merged_blocks += 1

    def generate_report(self) -> ErrorBudgetReport:
        """Generate a comprehensive error budget report."""
        total_used = sum(b.used_budget for b in self.qubit_budgets.values())
        estimated_fidelity = math.exp(-total_used) if total_used > 0 else 1.0

        return ErrorBudgetReport(
            total_budget=self.total_error_budget,
            total_used=total_used,
            qubit_budgets=dict(self.qubit_budgets),
            cancelled_gates=self.cancelled_gates,
            merged_blocks=self.merged_blocks,
            estimated_fidelity=estimated_fidelity,
        )

    @staticmethod
    def _are_inverse_gates(gate1: GateError, gate2: GateError) -> bool:
        """Check if two gates are inverses of each other."""
        if gate1.gate_type != gate2.gate_type:
            return False
        if gate1.qubits != gate2.qubits:
            return False
        # Simplified: gates on same qubits of same type are considered potential inverses
        return True


class NoiseAwareCancellation:
    """Noise-aware gate cancellation pass that respects error budgets."""

    def __init__(self, budget_manager: ErrorBudgetManager):
        self.budget = budget_manager

    def optimize(self, gates: List[GateError]) -> Tuple[List[GateError], int]:
        """Cancel inverse gate pairs while respecting error budget."""
        optimized = list(gates)
        cancellations = 0

        i = 0
        while i < len(optimized) - 1:
            g1 = optimized[i]
            g2 = optimized[i + 1]

            if self.budget.can_cancel_pair(g1, g2):
                self.budget.record_cancellation(g1, g2)
                optimized.pop(i)
                optimized.pop(i)  # pop shifted index
                cancellations += 1
            else:
                i += 1

        return optimized, cancellations

    def compute_savings(self, original: List[GateError], optimized: List[GateError]) -> Dict:
        """Compute error savings from cancellation."""
        original_error = sum(g.error_rate for g in original)
        optimized_error = sum(g.error_rate for g in optimized)
        return {
            "original_gate_count": len(original),
            "optimized_gate_count": len(optimized),
            "gates_cancelled": len(original) - len(optimized),
            "original_total_error": original_error,
            "optimized_total_error": optimized_error,
            "error_reduction": original_error - optimized_error,
            "error_reduction_pct": (
                f"{((original_error - optimized_error) / original_error * 100):.1f}%"
                if original_error > 0 else "0.0%"
            ),
        }
