# Qiskit Circuit Transpiler Agent

A Python project with two complementary tools: a numerical threshold-audit service and experimental quantum-circuit routing and optimization utilities. A standalone browser demo illustrates sequential two-qubit SWAP routing over simple coupling graphs.

**Important:** Despite the repository name, the current implementation does **not** call Qiskit's `transpile()` or execute OpenQASM circuits. The routing and Pareto calculations are illustrative heuristics, not hardware-validated quantum compilation. The browser demo performs its own local calculations and does not call the Python server.

## Features

- Deterministic, shortest-path routing of ordered two-qubit interactions with validated initial qubit placement; SWAP count and serial two-qubit-gate count proxy.
- Illustrative backend registry (Eagle, Heron, Forte, Ankaa-2); topology and error values are synthetic examples **not** device calibration.
- Pareto analysis using simulated reductions in depth/gate count and a simple multiplicative fidelity estimator.
- Error-budget accounting and conservative cancellation of explicitly named self-inverse/inverse gate pairs.
- Separate multi-worker numerical threshold auditing with FastAPI endpoints, CLI and CSV batch mode.
- In-memory HMAC-SHA256 hash-chained audit log, requiring `AUDIT_SECRET_KEY` for durable verification across restarts.
- Local-only browser routing demonstration in `web/index.html`, with JSON export.

## Browser demonstration

Open `web/index.html` in a modern browser. Choose 2–16 qubits and a line, ring or all-to-all topology, then enter two-qubit interactions as lines of `0,3`. **Route circuit** computes the inserted SWAP operations; **Export JSON** saves the result.

The demo uses an identity initial mapping and a uniform user-supplied error assumption. Its fidelity proxy covers inserted SWAPs only, excluding original gate errors, readout and parallel scheduling. All inputs remain local; no external API, user account or network access is required. The static `web/` directory is suitable for GitHub Pages once Pages is enabled for the repository and the deployment workflow succeeds.

## Python installation

Requires Python 3.10–3.12 (the tested CI matrix). From the repository root:

```bash
python -m pip install -e ".[dev]"
python -m pytest -v
node --test tests/test_web.cjs  # optional: Node.js for browser logic tests
```

For production without test tools: `python -m pip install .`.

## Command-line examples

The original generic threshold-audit CLI remains available:

```bash
python cli.py audit --task-id TASK-001 --target TARGET-01 --primary 28.4 --secondary 14.2 --critical --status DISCORDANT
python cli.py chat "What standard is applied?"
python cli.py batch -i sample.csv -o results.csv
python cli.py verify-audit
python cli.py serve --host 127.0.0.1 --port 8000
```

The parallel quantum-domain threshold evaluator is available as `python qiskit_transpiler_app.py audit`; it evaluates scalar parameters, **not** a QASM circuit.

The server exposes `GET /health`, `GET /metrics`, `POST /api/audit`, `POST /api/chat`, and `GET /api/audit/logs`. FastAPI's interactive reference is at `/docs`. `POST /api/audit` accepts fields defined in `agents/models.py`; `sample_payload.json` provides an example. Inputs with identified sensitive patterns are rejected by the heuristic guard, which is not comprehensive PHI de-identification.

Batch input and output files must remain within the current working directory; non-boolean values in `is_critical_flag` are rejected.

## Security and deployment

Set a private signing key through the runtime environment, never in source control:

```bash
export AUDIT_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
docker compose up --build
```

The Docker Compose file requires this environment variable. If the key is omitted in direct local Python execution, a warning is issued and an ephemeral key is generated; old signatures cannot be verified after restart. Audit records are stored only in process memory and are **not** durable evidence or a complete production compliance solution. Do not submit patient data or credentials. Production deployments should add access control, rate limits and persistent, access-controlled audit storage.

The Python API requires a running server and therefore cannot be hosted directly on static GitHub Pages. The Pages workflow publishes **only** the client-side `web/` demo.

## Project layout

- `agents/`: generic task auditors, audit signatures, metrics and FastAPI service.
- `qiskit_transpiler/`: quantum-domain data models, topology registry, routing, error budgets, Pareto estimators and separate CLI.
- `web/`: dependency-free static interactive routing demo.
- `tests/`: Python and JavaScript regression tests.
- `cli.py`, `simulator.py`, `enrichment.py`: batch entry points, synthetic test generator and legacy threshold examples.

## Compatibility, limitations and license

The browser demo works with current Chromium, Firefox and Safari JavaScript engines. The Python routing algorithm is a deterministic shortest-path heuristic, not Qiskit's SABRE. Hardware topologies and fidelity figures should not be used to benchmark real quantum devices. The legacy threshold services are not clinical decision systems.

MIT license; see [LICENSE](LICENSE).
