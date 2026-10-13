"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { parseInteractions, makeNeighbors, shortestPath, routeCircuit } = require("../web/app.js");

test("input parser validates comma-separated zero-based qubits", () => {
  assert.deepEqual(parseInteractions("0,3\n1,2", 4), [[0, 3], [1, 2]]);
  assert.throws(() => parseInteractions("0,4", 4), /in range/);
  assert.throws(() => parseInteractions("2,2", 4), /different/);
  assert.throws(() => parseInteractions("hello", 4), /integers/);
  assert.throws(() => parseInteractions("", 4), /at least one/);
});
test("illustrative topologies construct expected connectivity", () => {
  assert.deepEqual(makeNeighbors(3, "line"), [[1], [0, 2], [1]]);
  assert.deepEqual(shortestPath(makeNeighbors(4, "ring"), 0, 3), [0, 3]);
  assert.deepEqual(makeNeighbors(3, "all"), [[1, 2], [0, 2], [0, 1]]);
  assert.throws(() => makeNeighbors(0, "line"), /between 2 and 16/);
});
test("routing respects original interaction order and provides valid sites", () => {
  const result = routeCircuit({
    numQubits: 4, topology: "line", edges: [[0, 3], [0, 1], [1, 3]], errorRate: 0.01
  });
  assert.deepEqual(result.interactions.map(x => x.logicalQubits), [[0, 3], [0, 1], [1, 3]]);
  assert.ok(result.swapCount >= 1);
  assert.equal(result.serialTwoQGateProxy, 3 + 3 * result.swapCount);
  assert.equal(new Set(result.finalLogicalToPhysical).size, 4);
  for (const gate of result.interactions) {
    assert.equal(Math.abs(gate.physicalQubits[0] - gate.physicalQubits[1]), 1);
  }
  assert.ok(result.swapOnlyFidelityProxy <= 1 && result.swapOnlyFidelityProxy > 0);
});
test("fully connected graph needs no SWAPs", () => {
  const result = routeCircuit({
    numQubits: 4, topology: "all", edges: [[0, 3], [1, 2]], errorRate: 0.01
  });
  assert.equal(result.swapCount, 0);
  assert.equal(result.serialTwoQGateProxy, 2);
  assert.equal(result.swapOnlyFidelityProxy, 1);
});
test("invalid inputs are rejected, not shown as simulated success", () => {
  assert.throws(() => routeCircuit({ numQubits: 3, topology: "line", edges: [[1, 3]], errorRate: .01 }), /invalid/);
  assert.throws(() => routeCircuit({ numQubits: 3, topology: "line", edges: [[0, 1]], errorRate: NaN }), /probability/);
  assert.throws(() => routeCircuit({ numQubits: 3, topology: "line", edges: [[0, 1]], errorRate: 1 }), /probability/);
});
