import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from qiskit_transpiler.models import FrontierPayload, ExecutionStatus
from qiskit_transpiler.engine import FrontierDomainEngine
from qiskit_transpiler.agents import QubitMappingAgent, GateDepthOptimizerAgent, CommutationCancellationAgent, TranspilerCoordinator
from qiskit_transpiler.cli import main, _safe_resolve_path


def test_sub_agents():
    a1 = QubitMappingAgent()
    p1 = FrontierPayload("T1", "KEY-01", primary_metric=35.0, secondary_metric=4.0, status_descriptor="NOMINAL")
    alerts1 = a1.audit(p1)
    assert len(alerts1) == 1
    assert alerts1[0].status == ExecutionStatus.ELEVATED_RISK

    a2 = GateDepthOptimizerAgent()
    p2 = FrontierPayload("T2", "KEY-02", primary_metric=10.0, secondary_metric=15.0, status_descriptor="NOMINAL", is_critical_flag=True)
    alerts2 = a2.audit(p2)
    assert len(alerts2) == 1
    assert alerts2[0].status == ExecutionStatus.CRITICAL_INTERVENTION

    a3 = CommutationCancellationAgent()
    p3 = FrontierPayload("T3", "KEY-03", primary_metric=10.0, secondary_metric=4.0, status_descriptor="DISCORDANT_ANOMALY")
    alerts3 = a3.audit(p3)
    assert len(alerts3) == 1


def test_coordinator():
    coord = TranspilerCoordinator()
    p_nominal = FrontierPayload("T4", "KEY-04", primary_metric=12.0, secondary_metric=4.0, status_descriptor="NOMINAL")
    dossier = coord.process(p_nominal)
    assert dossier["overall_status"] == ExecutionStatus.NOMINAL.value
    assert dossier["total_alerts"] == 0

    ans = coord.query_supervisory_chat("What standard is applied?")
    assert "OpenQASM 3.0 / Qiskit Transpiler Standard" in ans or "specifications" in ans


def test_cli():
    assert main(["audit", "--task-id", "CLI-01"]) == 0
    assert main(["chat", "What", "is", "the", "system", "status?"]) == 0


def test_safe_path_resolution():
    """Test that path traversal is blocked in qiskit_transpiler CLI."""
    # Normal path should work
    p = _safe_resolve_path("sample.csv", must_exist=True)
    assert p.exists()

    # Path traversal should be blocked
    with pytest.raises(ValueError, match="Path traversal detected"):
        _safe_resolve_path("../../etc/passwd")

    with pytest.raises(ValueError, match="Path traversal detected"):
        _safe_resolve_path("../../../windows/system32/config/sam")


def test_coordinator_all_alert_levels():
    """Test coordinator produces correct alert levels for different inputs."""
    coord = TranspilerCoordinator()

    # Nominal case - no alerts
    p_nominal = FrontierPayload("N1", "KEY-N1", primary_metric=10.0, secondary_metric=4.0, status_descriptor="NOMINAL")
    d = coord.process(p_nominal)
    assert d["overall_status"] == ExecutionStatus.NOMINAL.value
    assert d["total_alerts"] == 0

    # Critical case
    p_critical = FrontierPayload("C1", "KEY-C1", primary_metric=35.0, secondary_metric=15.0, status_descriptor="ANOMALY", is_critical_flag=True)
    d = coord.process(p_critical)
    assert d["overall_status"] == ExecutionStatus.CRITICAL_INTERVENTION.value
    assert d["critical_count"] > 0
