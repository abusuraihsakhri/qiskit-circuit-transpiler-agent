# Qiskit Circuit Transpiler Agent

> **Domain:** Quantum Computing
> **Standard:** OpenQASM 3.0 / Qiskit Transpiler Standard

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB.svg?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688.svg?logo=fastapi&logoColor=white)
![Audit Trail](https://img.shields.io/badge/Audit-HMAC--SHA256_Tamper--Evident-brightgreen.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg?logo=docker&logoColor=white)

</div>

---

## 📖 What It Does

Qiskit Circuit Transpiler Agent is a multi-agent quantum circuit analysis and transpilation optimization framework. It evaluates quantum circuit parameters against operational thresholds, optimizes CNOT gate depth, and provides Pareto-optimal tradeoffs between circuit depth and estimated fidelity.

---

## ⚙️ Key Capabilities & Algorithmic Modules

- **Multi-Agent Circuit Analysis**: Three specialized sub-agents audit qubit mapping, gate depth, and protocol conformance
- **Error Budget Manager**: Tracks per-qubit and per-gate error allocation during transpilation
- **Pareto Optimization**: Multi-objective optimization across transpilation optimization levels
- **Noise-Aware Gate Cancellation**: Cancels inverse gate pairs while respecting error budgets
- **HMAC-SHA256 Audit Trail**: Cryptographically signed, tamper-evident logging
- **FastAPI REST Server**: OpenAPI endpoints for circuit evaluation and chat

---

## 💻 Installation

```bash
pip install -e .
```

For development (includes test dependencies):
```bash
pip install -e ".[dev]"
```

---

## 💻 CLI Quickstart & Usage

### 1. Single Task Evaluation
```bash
python cli.py audit --task-id TASK-001 --target TARGET-01 --primary 28.5 --secondary 14.2 --critical --status DISCORDANT
```

### 2. System Chat
```bash
python cli.py chat "What standard is applied?"
```

### 3. Batch Processing
```bash
python cli.py batch -i sample.csv -o results.csv
```

### 4. Verify Audit Trail
```bash
python cli.py verify-audit
```

### 5. Launch REST Server
```bash
python cli.py serve --host 127.0.0.1 --port 8000
```

### Parameter Reference
- `--task-id`: Unique task identifier
- `--target`: Target qubit or circuit identifier
- `--primary`: Primary domain measurement or score
- `--secondary`: Secondary confidence or kinetic score
- `--critical`: Flag for critical safety interlock
- `--status`: Status descriptor (NOMINAL, DISCORDANT, ANOMALY, etc.)

---

## 🛡️ Security & Architecture

- **Tamper-Evident HMAC-SHA256 Audit Trail**: Chained, cryptographically signed logs
- **Path Traversal Protection**: Safe file path resolution in batch mode
- **Ephemeral Key Fallback**: Secure random key generation when `AUDIT_SECRET_KEY` is not set
- **FastAPI & Prometheus Telemetry**: Exposes REST endpoints and operational metrics

### Environment Variables
- `AUDIT_SECRET_KEY`: Secret key for HMAC-SHA256 audit signatures (recommended for production)

---

## 🧪 Testing & Verification

Run the automated test suite:
```bash
pytest -v
```

Execute high-throughput batch simulation benchmarks:
```bash
python simulator.py 100
```

---

## 🐳 Container Deployment

```bash
docker build -t qiskit-circuit-transpiler-agent .
docker run -p 8000:8000 qiskit-circuit-transpiler-agent
```

---

## 📁 Project Structure

```
qiskit-circuit-transpiler-agent/
├── agents/                  # Core multi-agent system (Clinical/Biomedical AI agent)
│   ├── base.py             # Security, PHI guard, HMAC audit
│   ├── models.py           # Pydantic data models
│   ├── supervisor.py       # Master orchestrator
│   ├── workers.py          # Specialized worker agents
│   ├── api.py              # FastAPI REST server
│   └── ...
├── qiskit_transpiler/      # Quantum circuit transpiler module
│   ├── engine.py           # Domain evaluation engine
│   ├── agents.py           # Transpiler sub-agents
│   ├── error_budget.py     # Error budget management
│   ├── pareto_optimizer.py # Pareto frontier optimization
│   └── server.py           # FastAPI app factory
├── tests/                  # Test suite
├── cli.py                  # Main CLI entry point
├── simulator.py            # High-throughput simulation
└── enrichment.py           # Enrichment feature engines
```
