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
        """Route a circuit onto the hardware using SABRE algorithm."""
        if initial_mapping is None:
            initial_mapping = self._greedy_initial_mapping(circuit_edges, num_qubits)

        # Build reverse mapping
        logical_to_physical = dict(initial_mapping)
        physical_to_logical = {v: k for k, v in logical_to_physical.items()}

        swap_ops: List[SwapOperation] = []
        remaining_edges = list(circuit_edges)
        layer = 0

        while remaining_edges:
            # Find executable gates (both qubits adjacent on hardware)
            executable = []
            non_executable = []
            for q1, q2 in remaining_edges:
                p1, p2 = logical_to_physical[q1], logical_to_physical[q2]
                if self.coupling_map.is_connected(p1, p2):
                    executable.append((q1, q2))
                else:
                    non_executable.append((q1, q2))

            if not non_executable:
                break

            # Find best SWAP to insert
            best_swap = self._find_best_swap(logical_to_physical, non_executable)
            if best_swap is None:
                break

            # Apply SWAP
            lq1, lq2 = best_swap
            p1, p2 = logical_to_physical[lq1], logical_to_physical[lq2]
            cost = self.coupling_map.edge_error(p1, p2)
            swap_ops.append(SwapOperation(p1, p2, cost, layer))

            # Update mappings
            logical_to_physical[lq1], logical_to_physical[lq2] = p2, p1
            remaining_edges = non_executable
            layer += 1

        # Compute fidelity estimate
        total_error = sum(s.cost for s in swap_ops)
        fidelity = math.exp(-total_error) if swap_ops else 1.0

        return RoutingResult(
            initial_mapping=initial_mapping,
            swap_operations=swap_ops,
            total_swap_count=len(swap_ops),
            total_cnot_depth=len(swap_ops) + len(circuit_edges),
            total_routing_cost=sum(s.cost for s in swap_ops),
            fidelity_estimate=fidelity,
        )

    def _greedy_initial_mapping(self, circuit_edges: List[Tuple[int, int]], num_qubits: int) -> Dict[int, int]:
        """Greedy initial qubit placement based on circuit structure."""
        # Build circuit adjacency
        adj: Dict[int, Set[int]] = {i: set() for i in range(num_qubits)}
        for q1, q2 in circuit_edges:
            adj[q1].add(q2)
            adj[q2].add(q1)

        # Sort by degree (highest first)
        sorted_qubits = sorted(range(num_qubits), key=lambda q: -len(adj[q]))

        # Map to hardware qubits with highest connectivity
        hw_degrees = [(len(self.coupling_map.neighbors(i)), i) for i in range(self.coupling_map.num_qubits)]
        hw_degrees.sort(reverse=True)

        mapping = {}
        for i, logical_q in enumerate(sorted_qubits):
            if i < len(hw_degrees):
                mapping[logical_q] = hw_degrees[i][1]

        return mapping

    def _find_best_swap(
        self,
        logical_to_physical: Dict[int, int],
        remaining_edges: List[Tuple[int, int]],
    ) -> Optional[Tuple[int, int]]:
        """Find the best SWAP operation to reduce total routing cost."""
        best_cost = float('inf')
        best_swap = None

        # Collect physical qubits involved in remaining edges
        involved_physical: Set[int] = set()
        for q1, q2 in remaining_edges:
            involved_physical.add(logical_to_physical[q1])
            involved_physical.add(logical_to_physical[q2])

        # Try all SWAPs on adjacent qubits
        for p1 in involved_physical:
            for p2 in self.coupling_map.neighbors(p1):
                if p2 in involved_physical:
                    continue
                # Compute cost of this SWAP
                cost = self._swap_cost(p1, p2, logical_to_physical, remaining_edges)
                if cost < best_cost:
                    best_cost = cost
                    # Find logical qubits at these physical positions
                    lq1 = next((lq for lq, pp in logical_to_physical.items() if pp == p1), None)
                    lq2 = next((lq for lq, pp in logical_to_physical.items() if pp == p2), None)
                    if lq1 is not None and lq2 is not None:
                        best_swap = (lq1, lq2)

        return best_swap

    def _swap_cost(
        self,
        p1: int,
        p2: int,
        logical_to_physical: Dict[int, int],
        remaining_edges: List[Tuple[int, int]],
    ) -> float:
        """Compute the cost of inserting a SWAP between physical qubits p1 and p2."""
        # Simulate the SWAP
        new_mapping = dict(logical_to_physical)
        lq1 = next((lq for lq, pp in new_mapping.items() if pp == p1), None)
        lq2 = next((lq for lq, pp in new_mapping.items() if pp == p2), None)
        if lq1 is not None and lq2 is not None:
            new_mapping[lq1], new_mapping[lq2] = p2, p1

        # Compute new total distance
        total_dist = 0.0
        for q1, q2 in remaining_edges:
            np1, np2 = new_mapping[q1], new_mapping[q2]
            if self.coupling_map.is_connected(np1, np2):
                total_dist += 0.0
            else:
                total_dist += 1.0

        # Add SWAP gate error cost
        swap_error = self.coupling_map.edge_error(p1, p2)
        return total_dist + swap_error * 10


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
