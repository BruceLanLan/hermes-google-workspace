#!/usr/bin/env node
/**
 * Thin npm entrypoint: runs setup.py with the same argv.
 * Override interpreter: GWS_PYTHON=/path/to/python
 */
const { spawnSync } = require("child_process");
const path = require("path");

const root = path.join(__dirname, "..");
const script = path.join(root, "scripts", "setup.py");
const py = process.env.GWS_PYTHON || "python3";

const result = spawnSync(py, [script, ...process.argv.slice(2)], {
  stdio: "inherit",
  env: process.env,
  windowsHide: true,
});

if (result.error) {
  console.error(result.error.message);
  process.exit(1);
}

process.exit(result.status === null ? 1 : result.status);
