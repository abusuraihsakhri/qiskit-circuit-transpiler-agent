"""
Circuit Depth vs Fidelity Pareto Optimization.
Multi-objective optimization across transpilation optimization levels.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import IntEnum


class OptimizationLevel(IntEnum):
    LEVEL_0 = 0  # No optimization
    LEVEL_1 = 1  # Light optimization
    LEVEL_2 = 2  # Medium optimization
    LEVEL_3 = 3  # Heavy optimization


@dataclass
class TranspilationResult:
    """Result of transpilation at a specific optimization level."""
    optimization_level: OptimizationLevel
    gate_count: int
    circuit_depth: int
    cnot_count: int
    estimated_fidelity: float
    transpilation_time_ms: float

    def to_dict(self) -> Dict:
        return {
            "optimization_level": self.optimization_level.name,
            "gate_count": self.gate_count,
            "circuit_depth": self.circuit_depth,
            "cnot_count": self.cnot_count,
            "estimated_fidelity": self.estimated_fidelity,
            "transpilation_time_ms": self.transpilation_time_ms,
        }


@dataclass
class ParetoPoint:
    """A point on the Pareto frontier."""
    depth: int
    fidelity: float
    result: TranspilationResult
    is_dominated: bool = False

    def dominates(self, other: "ParetoPoint") -> bool:
        """Check if this point dominates another (lower depth AND higher fidelity)."""
        return (self.depth <= other.depth and self.fidelity >= other.fidelity and
                (self.depth < other.depth or self.fidelity > other.fidelity))


@dataclass
class ParetoFrontier:
    """The Pareto frontier of depth vs fidelity tradeoffs."""
    points: List[ParetoPoint]
    dominated_points: List[ParetoPoint]

    @property
    def frontier_size(self) -> int:
        return len(self.points)

    def best_fidelity(self) -> Optional[ParetoPoint]:
        """Get the point with highest fidelity."""
        return max(self.points, key=lambda p: p.fidelity) if self.points else None

    def best_depth(self) -> Optional[ParetoPoint]:
        """Get the point with lowest depth."""
        return min(self.points, key=lambda p: p.depth) if self.points else None

    def select_optimal(self, max_depth: Optional[int] = None, min_fidelity: Optional[float] = None) -> Optional[ParetoPoint]:
        """Select the optimal point given user constraints."""
        candidates = self.points
        if max_depth is not None:
            candidates = [p for p in candidates if p.depth <= max_depth]
        if min_fidelity is not None:
            candidates = [p for p in candidates if p.fidelity >= min_fidelity]

        if not candidates:
            return None

        # Among valid candidates, pick highest fidelity
        return max(candidates, key=lambda p: p.fidelity)

    def to_dict(self) -> Dict:
        return {
            "frontier_size": self.frontier_size,
            "frontier_points": [
                {"depth": p.depth, "fidelity": p.fidelity, "level": p.result.optimization_level.name}
                for p in self.points
            ],
            "dominated_count": len(self.dominated_points),
        }


class FidelityEstimator:
    """Estimates circuit fidelity from gate error rates."""

    def __init__(self, single_qubit_error: float = 0.0003, two_qubit_error: float = 0.008, readout_error: float = 0.01):
        self.single_qubit_error = single_qubit_error
        self.two_qubit_error = two_qubit_error
        self.readout_error = readout_error

    def estimate(
        self,
        single_qubit_count: int,
        two_qubit_count: int,
        num_measurements: int = 0,
    ) -> float:
        """Estimate overall circuit fidelity: F = prod(1 - err_i)."""
        f_single = (1.0 - self.single_qubit_error) ** single_qubit_count
        f_two = (1.0 - self.two_qubit_error) ** two_qubit_count
        f_readout = (1.0 - self.readout_error) ** max(num_measurements, 1)
        return f_single * f_two * f_readout

    def estimate_from_result(self, result: TranspilationResult, num_measurements: int = 0) -> float:
        """Estimate fidelity from a transpilation result."""
        single_count = result.gate_count - result.cnot_count
        return self.estimate(single_count, result.cnot_count, num_measurements)


class ParetoOptimizer:
    """Multi-objective Pareto optimization across optimization levels."""

    def __init__(self, fidelity_estimator: Optional[FidelityEstimator] = None):
        self.fidelity_estimator = fidelity_estimator or FidelityEstimator()

    def optimize(
        self,
        base_gate_count: int,
        base_depth: int,
        base_cnot_count: int,
        num_qubits: int,
    ) -> ParetoFrontier:
        """Run transpilation at multiple optimization levels and build Pareto frontier."""
        results = []

        for level in OptimizationLevel:
            result = self._simulate_transpilation(level, base_gate_count, base_depth, base_cnot_count, num_qubits)
            results.append(result)

        # Build Pareto frontier
        points = []
        for r in results:
            fidelity = self.fidelity_estimator.estimate_from_result(r)
            points.append(ParetoPoint(depth=r.circuit_depth, fidelity=fidelity, result=r))

        # Identify Pareto-optimal points
        frontier_points = []
        dominated_points = []

        for p in points:
            is_dominated = False
            for q in points:
                if q.dominates(p):
                    is_dominated = True
                    break
            p.is_dominated = is_dominated
            if is_dominated:
                dominated_points.append(p)
            else:
                frontier_points.append(p)

        # Sort frontier by depth
        frontier_points.sort(key=lambda p: p.depth)

        return ParetoFrontier(points=frontier_points, dominated_points=dominated_points)

    def _simulate_transpilation(
        self,
        level: OptimizationLevel,
        base_gate_count: int,
        base_depth: int,
        base_cnot_count: int,
        num_qubits: int,
    ) -> TranspilationResult:
        """Simulate transpilation at a given optimization level."""
        # Optimization level factors
        reduction_factors = {
            OptimizationLevel.LEVEL_0: (1.0, 1.0, 1.0),
            OptimizationLevel.LEVEL_1: (0.9, 0.85, 0.95),
            OptimizationLevel.LEVEL_2: (0.75, 0.7, 0.85),
            OptimizationLevel.LEVEL_3: (0.6, 0.5, 0.75),
        }

        gate_factor, depth_factor, cnot_factor = reduction_factors[level]
        time_factors = {0: 10, 1: 50, 2: 200, 3: 800}

        return TranspilationResult(
            optimization_level=level,
            gate_count=max(1, int(base_gate_count * gate_factor)),
            circuit_depth=max(1, int(base_depth * depth_factor)),
            cnot_count=max(0, int(base_cnot_count * cnot_factor)),
            estimated_fidelity=0.0,  # Will be computed by caller
            transpilation_time_ms=time_factors[level.value] + num_qubits * level.value,
        )
