"use strict";

/** Parse ordered logical two-qubit interactions from comma-separated lines. */
function parseInteractions(text, numQubits) {
  if (typeof text !== "string" || !text.trim()) {
    throw new Error("Enter at least one interaction.");
  }
  return text.trim().split(/\r?\n/).map((line, index) => {
    const match = /^\s*(\d+)\s*,\s*(\d+)\s*$/.exec(line);
    if (!match) throw new Error("Line " + (index + 1) + ": enter two integers separated by a comma.");
    const a = Number(match[1]), b = Number(match[2]);
    if (a >= numQubits || b >= numQubits || a === b) {
      throw new Error("Line " + (index + 1) + ": qubits must be different and in range 0–" + (numQubits - 1) + ".");
    }
    return [a, b];
  });
}

/** Produce an undirected illustrative coupling map. */
function makeNeighbors(numQubits, topology) {
  if (!Number.isInteger(numQubits) || numQubits < 2 || numQubits > 16) {
    throw new Error("Qubit count must be an integer between 2 and 16.");
  }
  if (!["line", "ring", "all"].includes(topology)) {
    throw new Error("Unknown topology.");
  }
  const neighbors = Array.from({ length: numQubits }, () => []);
  for (let a = 0; a < numQubits; a++) {
    for (let b = a + 1; b < numQubits; b++) {
      const connected = topology === "all" || b === a + 1 ||
        (topology === "ring" && a === 0 && b === numQubits - 1);
      if (connected) {
        neighbors[a].push(b);
        neighbors[b].push(a);
      }
    }
  }
  return neighbors;
}

/** Return minimum-hop route on an undirected coupling graph. */
function shortestPath(neighbors, source, target) {
  const queue = [source], parent = new Map([[source, null]]);
  for (let index = 0; index < queue.length; index++) {
    const vertex = queue[index];
    if (vertex === target) {
      const route = [];
      for (let current = vertex; current !== null; current = parent.get(current)) {
        route.unshift(current);
      }
      return route;
    }
    for (const next of neighbors[vertex]) {
      if (!parent.has(next)) {
        parent.set(next, vertex);
        queue.push(next);
      }
    }
  }
  throw new Error("The hardware connectivity graph is disconnected.");
}

/** Route ordered interactions without changing gate order. */
function routeCircuit({ numQubits, topology, edges, errorRate }) {
  const neighbors = makeNeighbors(numQubits, topology);
  if (typeof errorRate !== "number" || !Number.isFinite(errorRate) || errorRate < 0 || errorRate >= 1) {
    throw new Error("Error probability must be finite and between 0 and 1 (exclusive of 1).");
  }
  if (!Array.isArray(edges) || edges.length === 0) throw new Error("Enter at least one interaction.");

  // Start with identity placement. As swaps are inserted, track both directions.
  const logicalToPhysical = Array.from({ length: numQubits }, (_, q) => q);
  const physicalToLogical = Array.from({ length: numQubits }, (_, q) => q);
  const swaps = [];
  const executed = [];
  edges.forEach((edge, gateIndex) => {
    if (!Array.isArray(edge) || edge.length !== 2 || !edge.every(
      q => Number.isInteger(q) && q >= 0 && q < numQubits
    ) || edge[0] === edge[1]) {
      throw new Error("Interaction " + (gateIndex + 1) + " contains invalid qubit IDs.");
    }
    const [first, second] = edge;
    while (!neighbors[logicalToPhysical[first]].includes(logicalToPhysical[second])) {
      const path = shortestPath(neighbors, logicalToPhysical[first], logicalToPhysical[second]);
      const [physicalA, physicalB] = path;
      const logicalA = physicalToLogical[physicalA], logicalB = physicalToLogical[physicalB];
      [physicalToLogical[physicalA], physicalToLogical[physicalB]] = [logicalB, logicalA];
      logicalToPhysical[logicalA] = physicalB;
      logicalToPhysical[logicalB] = physicalA;
      swaps.push({ beforeGate: gateIndex + 1, physicalQubits: [physicalA, physicalB] });
    }
    executed.push({
      gate: gateIndex + 1,
      logicalQubits: [first, second],
      physicalQubits: [logicalToPhysical[first], logicalToPhysical[second]]
    });
  });
  return {
    model: "deterministic shortest-path routing (illustrative)",
    qubits: numQubits, topology, errorRate,
    interactions: executed,
    swaps,
    swapCount: swaps.length,
    serialTwoQGateProxy: edges.length + 3 * swaps.length,
    swapOnlyFidelityProxy: Math.exp(-3 * errorRate * swaps.length),
    finalLogicalToPhysical: logicalToPhysical
  };
}

if (typeof document !== "undefined") {
  const form = document.getElementById("route-form");
  const status = document.getElementById("status");
  const details = document.getElementById("details");
  const exportButton = document.getElementById("download");
  let lastResult = null;

  function renderResult(result) {
    lastResult = result;
    status.classList.remove("error");
    status.textContent = "Routed " + result.interactions.length + " interactions on a " + result.topology + " coupling graph.";
    document.getElementById("swap-count").textContent = String(result.swapCount);
    document.getElementById("depth").textContent = String(result.serialTwoQGateProxy);
    document.getElementById("fidelity").textContent = (result.swapOnlyFidelityProxy * 100).toFixed(2) + "%";
    details.textContent = JSON.stringify(result, null, 2);
    exportButton.disabled = false;
  }

  form.addEventListener("submit", event => {
    event.preventDefault();
    try {
      const numQubits = Number(document.getElementById("num-qubits").value);
      const errorRate = Number(document.getElementById("error-rate").value);
      renderResult(routeCircuit({
        numQubits,
        topology: document.getElementById("topology").value,
        edges: parseInteractions(document.getElementById("gates").value, numQubits),
        errorRate
      }));
    } catch (error) {
      lastResult = null;
      status.classList.add("error");
      status.textContent = error.message;
      details.textContent = "Input validation failed. No route was computed.";
      ["swap-count", "depth", "fidelity"].forEach(id => {
        document.getElementById(id).textContent = "—";
      });
      exportButton.disabled = true;
    }
  });

  document.getElementById("reset").addEventListener("click", () => {
    form.reset();
    lastResult = null;
    status.classList.remove("error");
    status.textContent = "Run the example to compute a route.";
    details.textContent = "No computation yet.";
    ["swap-count", "depth", "fidelity"].forEach(id => {
      document.getElementById(id).textContent = "—";
    });
    exportButton.disabled = true;
  });

  exportButton.addEventListener("click", () => {
    if (!lastResult) return;
    const blob = new Blob([JSON.stringify(lastResult, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "circuit-routing-result.json";
    anchor.click();
    URL.revokeObjectURL(url);
  });
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { parseInteractions, makeNeighbors, shortestPath, routeCircuit };
}
