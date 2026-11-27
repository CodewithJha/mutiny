import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import vm from "node:vm";
import React from "react";
import * as jsxRuntime from "react/jsx-runtime";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const testDirectory = path.dirname(fileURLToPath(import.meta.url));

function loadTypeScript(relativePath, dependencies = {}) {
  const source = readFileSync(path.join(testDirectory, "..", relativePath), "utf8");
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      jsx: ts.JsxEmit.ReactJSX,
      esModuleInterop: true,
    },
  });
  const exports = {};
  vm.runInNewContext(outputText, {
    exports,
    require(name) {
      assert.ok(Object.hasOwn(dependencies, name), `Unexpected import: ${name}`);
      return dependencies[name];
    },
    fetch() {
      assert.fail("Policies rendering must not make network requests");
    },
  }, { timeout: 1000 });
  return exports;
}

test("Policies renders local guidance without API access or an editor", () => {
  const codeBlock = loadTypeScript("src/components/ui/CodeBlock.tsx", {
    "react/jsx-runtime": jsxRuntime,
    react: React,
  });
  const { default: PoliciesPage } = loadTypeScript("src/app/policies/page.tsx", {
    "react/jsx-runtime": jsxRuntime,
    "@/components/ui/CodeBlock": codeBlock,
    "next/link": ({ href, children, ...props }) =>
      React.createElement("a", { ...props, href }, children),
  });
  const html = renderToStaticMarkup(React.createElement(PoliciesPage));
  assert.match(html, /Policies are managed locally/);
  assert.match(html, /mutiny init/);
  assert.match(html, /policy.yaml/);
  assert.match(html, /mutiny run --hosted/);
  assert.match(html, /mutiny test/);
  assert.match(html, /bundled demo uses its own sample policy/);
  assert.match(html, /href="\/campaigns"/);
  assert.match(html, /href="\/projects"/);
  assert.doesNotMatch(html, /<(input|textarea|form)\b/);
});

test("Hosted client no longer exposes retired policy file operations", () => {
  const { mutinyApi } = loadTypeScript("src/lib/api.ts");
  for (const method of ["policies", "policy", "policyContent", "savePolicyContent"]) {
    assert.equal(method in mutinyApi, false, `${method} must stay removed`);
  }
});

test("Regression names default to the violated rule, not the refund demo", () => {
  const { defaultRegressionName, DEFAULT_REGRESSION_NAME } = loadTypeScript("src/lib/api.ts");
  const hits = [
    { rule_id: "deny_send_email", violated: false },
    { rule_id: "delete_requires_confirm", violated: true },
    { rule_id: "refund_limit", violated: true },
  ];
  assert.equal(defaultRegressionName({ hits }), "delete_requires_confirm_regression");
  assert.equal(DEFAULT_REGRESSION_NAME, "discovered_violation");
  for (const candidate of [null, undefined, {}, { hits: [] }, { hits: [hits[0]] }]) {
    assert.equal(defaultRegressionName(candidate), DEFAULT_REGRESSION_NAME);
  }
  assert.equal(
    defaultRegressionName({ hits: [{ rule_id: "  ", violated: true }] }),
    DEFAULT_REGRESSION_NAME
  );
});
