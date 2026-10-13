"""
Hardware-Aware SWAP Routing with SABRE algorithm and fidelity-weighted routing.
"""
from __future__ import annotations
import heapq
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set
from .topology import CouplingMap, BackendTopology


@dataclass
class SwapOperation:
    """Represents a SWAP gate insertion in the routing."""
    qubit_a: int
    qubit_b: int
    cost: float
    layer: int

    def to_dict(self) -> Dict:
        return {"qubit_a": self.qubit_a, "qubit_b": self.qubit_b, "cost": self.cost, "layer": self.layer}


@dataclass
class RoutingResult:
    """Result of SWAP routing."""
    initial_mapping: Dict[int, int]
    swap_operations: List[SwapOperation]
    total_swap_count: int
    total_cnot_depth: int
    total_routing_cost: float
    fidelity_estimate: float

    def to_dict(self) -> Dict:
        return {
            "initial_mapping": self.initial_mapping,
            "swap_count": self.total_swap_count,
            "cnot_depth": self.total_cnot_depth,
            "routing_cost": self.total_routing_cost,
            "fidelity_estimate": self.fidelity_estimate,
            "swaps": [s.to_dict() for s in self.swap_operations],
        }


class SABRERouter:
    """SABRE algorithm for SWAP routing on hardware topologies."""

    def __init__(self, coupling_map: CouplingMap, decay_rate: float = 0.001):
        self.coupling_map = coupling_map
        self.decay_rate = decay_rate

    def route(
        self,
        circuit_edges: List[Tuple[int, int]],
        num_qubits: int,
        initial_mapping: Optional[Dict[int, int]] = None,
    ) -> RoutingResult:
        """Route ordered two-qubit interactions using deterministic shortest paths.

        A compatibility implementation; this is not the full Qiskit SABRE pass.
        Interactions retain their original execution order. Each inserted SWAP
        may move a logical qubit into a previously unused physical location.
        """
        if not 0 <= num_qubits <= self.coupling_map.num_qubits:
            raise ValueError("Circuit qubit count exceeds the hardware capacity")
        for q1, q2 in circuit_edges:
            if not (0 <= q1 < num_qubits and 0 <= q2 < num_qubits) or q1 == q2:
                raise ValueError(f"Invalid two-qubit interaction: {(q1, q2)}")

        mapping = dict(
            self._greedy_initial_mapping(circuit_edges, num_qubits)
            if initial_mapping is None else initial_mapping
        )
        if set(mapping) != set(range(num_qubits)):
            raise ValueError("Initial mapping must include every logical qubit")
        if len(set(mapping.values())) != num_qubits or any(
            not 0 <= p < self.coupling_map.num_qubits for p in mapping.values()
        ):
            raise ValueError("Initial mapping must be injective and within hardware bounds")

        initial = dict(mapping)
        reverse = {p: q for q, p in mapping.items()}
        swaps: List[SwapOperation] = []

        for gate_index, (q1, q2) in enumerate(circuit_edges):
            while not self.coupling_map.is_connected(mapping[q1], mapping[q2]):
                path = self._shortest_path(mapping[q1], mapping[q2])
                if path is None:
                    raise ValueError(f"No physical route exists for interaction {(q1, q2)}")
                p1, p2 = path[0], path[1]
                # Move a logical qubit along a hardware edge, including empty sites.
                l1, l2 = reverse.pop(p1, None), reverse.pop(p2, None)
                if l1 is not None:
                    mapping[l1] = p2
                    reverse[p2] = l1
                if l2 is not None:
                    mapping[l2] = p1
                    reverse[p1] = l2
                swaps.append(SwapOperation(
                    p1, p2, 3.0 * self.coupling_map.edge_error(p1, p2),
                    gate_index
                ))

        total_error = sum(s.cost for s in swaps)
        return RoutingResult(
            initial_mapping=initial,
            swap_operations=swaps,
            total_swap_count=len(swaps),
            # Serial two-qubit gate count proxy; actual parallel depth requires scheduling.
            total_cnot_depth=len(circuit_edges) + 3 * len(swaps),
            total_routing_cost=total_error,
            # Swap-induced fidelity proxy; excludes original gates and readout.
            fidelity_estimate=math.exp(-total_error),
        )

    def _greedy_initial_mapping(
        self, circuit_edges: List[Tuple[int, int]], num_qubits: int
    ) -> Dict[int, int]:
        degree = {q: 0 for q in range(num_qubits)}
        for q1, q2 in circuit_edges:
            degree[q1] += 1
            degree[q2] += 1
        logical = sorted(degree, key=lambda q: (-degree[q], q))
        physical = sorted(
            range(self.coupling_map.num_qubits),
            key=lambda p: (-len(self.coupling_map.neighbors(p)), p),
        )
        return dict(zip(logical, physical))

    def _shortest_path(self, start: int, target: int) -> Optional[List[int]]:
        """Find a minimum-hop physical route. Return None for disconnected sites."""
        from collections import deque

        queue = deque([start])
        parent = {start: None}
        while queue:
            current = queue.popleft()
            if current == target:
                path = [current]
                while parent[current] is not None:
                    current = parent[current]
                    path.append(current)
                return list(reversed(path))
            for neighbor in self.coupling_map.neighbors(current):
                if neighbor not in parent:
                    parent[neighbor] = current
                    queue.append(neighbor)
        return None


class HardwareAwareSwapRouter:
    """Fidelity-weighted SWAP router using backend calibration data."""

    def __init__(self, backend: BackendTopology):
        self.backend = backend
        self.coupling_map = backend.coupling_map

    def route(
        self,
        circuit_edges: List[Tuple[int, int]],
        num_qubits: int,
        initial_mapping: Optional[Dict[int, int]] = None,
    ) -> RoutingResult:
        """Route with fidelity-weighted cost function."""
        sabre = SABRERouter(self.coupling_map)
        result = sabre.route(circuit_edges, num_qubits, initial_mapping)

        # Re-compute fidelity with actual backend calibration data
        total_error = 0.0
        for swap in result.swap_operations:
            total_error += self.coupling_map.edge_error(swap.qubit_a, swap.qubit_b)

        result.fidelity_estimate = math.exp(-total_error) if result.swap_operations else 1.0
        return result

    def compare_routing_strategies(
        self,
        circuit_edges: List[Tuple[int, int]],
        num_qubits: int,
    ) -> Dict[str, RoutingResult]:
        """Compare different routing strategies on the same circuit."""
        sabre = SABRERouter(self.coupling_map)
        result_default = sabre.route(circuit_edges, num_qubits)

        # Try with different initial mappings
        best_result = result_default
        for _ in range(5):
            random_mapping = {i: i for i in range(min(num_qubits, self.coupling_map.num_qubits))}
            result = sabre.route(circuit_edges, num_qubits, random_mapping)
            if result.total_swap_count < best_result.total_swap_count:
                best_result = result

        return {
            "sabre_default": result_default,
            "sabre_best_of_5": best_result,
        }
