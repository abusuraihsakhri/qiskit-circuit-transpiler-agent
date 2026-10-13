"""Regression tests for routing, budgets, audit integrity and CSV input."""
import math

import pytest

from agents.base import AuditTrail
from cli import _parse_csv_bool as parse_primary_bool
from qiskit_transpiler.cli import _parse_csv_bool as parse_quantum_bool
from qiskit_transpiler.backends.topology import BackendFamily, BackendTopology, CouplingMap
from qiskit_transpiler.backends.swap_router import SABRERouter
from qiskit_transpiler.error_budget import (
    ErrorBudgetManager, GateError, GateType, NoiseAwareCancellation,
)
from qiskit_transpiler.pareto_optimizer import FidelityEstimator, ParetoOptimizer


def test_signed_audit_entries_reject_mutated_fields():
    trail = AuditTrail(secret_key="test-only-not-for-production")
    trail.log("user", "operator", "SUBMITTED", {"task": "A"})
    trail.log("worker", "system", "COMPLETE", {"task": "A"})
    assert trail.verify_integrity()
    exported = trail.get_trail()
    exported[0]["actor"] = "changed"
    assert trail.verify_integrity()  # Export is a snapshot, not a live reference.
    trail.logs[0]["actor"] = "changed"
    assert not trail.verify_integrity()


def test_audit_rejects_mutated_hash_and_missing_fields():
    trail = AuditTrail(secret_key="test")
    trail.log("actor", "tier", "EVENT", {"x": 1})
    trail.logs[0]["current_hash"] = "0" * 64
    assert not trail.verify_integrity()
    del trail.logs[0]["current_hash"]
    assert not trail.verify_integrity()


@pytest.mark.parametrize("parse", [parse_primary_bool, parse_quantum_bool])
def test_csv_boolean_values(parse):
    for value in ["False", " false ", "0", "NO", ""]:
        assert parse(value) is False
    for value in ["True", "1", "yes", "Y"]:
        assert parse(value) is True
    with pytest.raises(ValueError):
        parse("maybe")


def test_router_handles_fully_occupied_line():
    coupling = CouplingMap("line", 3, [(0, 1), (1, 2)])
    result = SABRERouter(coupling).route(
        [(0, 2)], 3, initial_mapping={0: 0, 1: 1, 2: 2}
    )
    assert result.total_swap_count == 1
    assert result.total_cnot_depth == 4
    assert result.swap_operations[0].qubit_a == 0
    assert result.swap_operations[0].qubit_b == 1
    assert 0 < result.fidelity_estimate <= 1


def test_router_uses_unoccupied_sites():
    coupling = CouplingMap("line", 4, [(0, 1), (1, 2), (2, 3)])
    result = SABRERouter(coupling).route(
        [(0, 1)], 2, initial_mapping={0: 0, 1: 3}
    )
    assert result.total_swap_count == 2


def test_router_rejects_bad_mapping_and_disconnected_graph():
    coupling = CouplingMap("split", 4, [(0, 1), (2, 3)])
    router = SABRERouter(coupling)
    with pytest.raises(ValueError, match="injective"):
        router.route([(0, 1)], 2, {0: 0, 1: 0})
    with pytest.raises(ValueError, match="No physical route"):
        router.route([(0, 1)], 2, {0: 0, 1: 3})
    with pytest.raises(ValueError, match="capacity"):
        router.route([], 5)


def test_subgraph_is_reindexed_and_weighted_distance_is_minimal():
    cmap = CouplingMap("weighted", 4, [(0, 1), (1, 2), (0, 2), (2, 3)],
                       gate_errors={(0, 1): .1, (1, 2): .1, (0, 2): .9, (2, 3): .2})
    backend = BackendTopology("demo", BackendFamily.SIMULATOR, cmap, ["cx"])
    assert math.isclose(backend.fidelity_weighted_distance(0, 2), .2)
    sub = cmap.subgraph([2, 3])
    assert sub.num_qubits == 2
    assert sub.is_connected(0, 1)
    assert sub.adjacency_matrix() == [[0, 1], [1, 0]]
    assert math.isclose(sub.edge_error(0, 1), .2)


def test_cancel_only_proven_inverse_gates():
    budget = ErrorBudgetManager(2, total_error_budget=.2)
    x = GateError(GateType.SINGLE_QUBIT, (0,), .02, 10, gate_name="x")
    h = GateError(GateType.SINGLE_QUBIT, (0,), .02, 10, gate_name="h")
    assert budget.record_gate(x)
    assert budget.record_gate(h)
    optimized, count = NoiseAwareCancellation(budget).optimize([x, h])
    assert count == 0 and optimized == [x, h]
    optimized, count = NoiseAwareCancellation(budget).optimize([x, x])
    assert count == 1 and not optimized


def test_budget_allocation_is_atomic():
    budget = ErrorBudgetManager(2, total_error_budget=.04)
    assert budget.record_gate(GateError(GateType.SINGLE_QUBIT, (0,), .02, 10, gate_name="h"))
    before = budget.qubit_budgets[1].used_budget
    rejected = GateError(GateType.TWO_QUBIT, (0, 1), .01, 20, gate_name="cx")
    assert not budget.record_gate(rejected)
    assert budget.qubit_budgets[1].used_budget == before
    assert len(budget.gate_log) == 1


def test_fidelity_estimator_and_invalid_circuit():
    estimator = FidelityEstimator()
    assert estimator.estimate(0, 0, 0) == 1.0
    with pytest.raises(ValueError):
        estimator.estimate(-1, 0)
    with pytest.raises(ValueError):
        ParetoOptimizer().optimize(2, 3, 4, 3)
