# MiniMax native qualification

## Environment

- Date: 2026-10-29.
- Platform: Linux x86_64.
- Node.js: 22.23.3.
- Host: official npm `@minimax-ai/code@0.6.9`, installed into an isolated temporary prefix.
- PowerContext: working-tree CLI and Server, with SQLite and a synthetic local Bearer credential.
- Targets: isolated temporary data directories, including spaces and Chinese characters. No personal MiniMax account, provider credentials, or user profile is used.

## Run

Install the CLI into an isolated prefix following the official [installation instructions](https://github.com/MiniMax-AI/minimax-code/blob/main/docs/installation.md), then run:

```bash
POWERCONTEXT_MINIMAX_ACCEPTANCE_COMMAND=/absolute/path/to/mcode \
  uv run python -m pytest tests/e2e/test_minimax_host.py -q \
  --basetemp=/tmp/powercontext-minimax-acceptance
```

The tests start a real PowerContext HTTP Server and invoke the public setup/doctor commands with the real MiniMax executable. The loopback listener must be permitted by the execution environment. Without the explicit launcher environment variable, these opt-in tests skip; a skip is not qualification.

## Qualification status

The local Linux reference run passes eleven scenarios against the real CLI: explicit destination, `MINIMAX_DATA_DIR`, `MAVIS_DATA_DIR`, invalid-package/authentication diagnostics, private and plugin MCP calls under both cold and preflight startup, disabled private overrides with and without Authorization, and diagnosis of an uninstalled target. They verify repeated setup, the native loader's enabled local plugin record, required Skill/MCP counts, saved-target reuse, native disablement and its preservation during setup, omission of an invalid native manifest, and rejection of a wrong private Bearer header by the real Server.

**Plugin-only tool injection remains unqualified for reliable use.** An independent Linux run with CLI 0.6.9 and Node.js 22.23.3 reports a connected, enabled plugin whose PowerContext tools never reach the model. The private-only case passes in that environment. Local passing runs do not resolve this failure, and this record does not establish reliable dual-route support.

Native discovery runs in a disposable profile containing the installed package and its enablement state. The real MiniMax profile is unchanged byte-for-byte across doctor, both before and after disabling the plugin through the real CLI. Diagnosing an uninstalled target does not create that target. Only the selected plugin's enablement is carried into the diagnostic runtime; real sessions and provider configuration are not imported.

The disabled-private scenarios configure the incoming package to use an anonymous loopback Server while retaining a disabled private HTTPS endpoint. First and repeated setup preserve every byte of the private file, including a dormant credential when present. Real native discovery and CLI Server probes succeed against the bundled endpoint, and doctor leaves the file unchanged.

The native tool scenarios first verify that setup synchronized the private and installed plugin MCP URLs and Authorization headers. Each case then isolates one connection before running `mcode exec` with a local OpenAI-compatible inference fixture:

| Case | Private MCP configuration | Native plugin state |
| --- | --- | --- |
| `private-mcp` | Retain the enabled `powercontext` entry | Disable `powercontext@local` through the real CLI |
| `plugin-mcp` | Remove the `powercontext` entry from the temporary profile | Keep `powercontext@local` enabled |

The real plugin list must confirm the expected enablement state. Each route runs with two startup modes. `cold` starts the native execution without a separate MCP preflight. `preflight` first uses an independent authenticated MCP client to initialize a real session and list tools at the configured endpoint, requiring `list_scopes` to be present. Preflight establishes Server MCP readiness; it does not populate the native process's connection cache or prove native tool injection. Each case uses a fresh Server database and native profile.

The inference fixture selects the single discovered `list_scopes` tool, either directly or through `tool_search` and `mcp_invoke`. Empty, missing, or ambiguous tools fail qualification. Tool aliases are not used to identify the route. A successful case requires the seeded Scope ID and title in the result associated with the emitted MCP tool-call ID. The result parser reads both the initial text block and appended MCP structured content. The plugin case also requires the installed Skill to reach the model; the private case does not require a Skill from its disabled plugin. These assertions establish an authenticated call for that execution, without an external model provider.

The fixed five-round local matrix at `f4345d04` completed all twenty executions successfully:

| Startup | Route | Successful executions | Maximum observed native `tools/list` response duration |
| --- | --- | --- | --- |
| Cold | Private MCP | 5/5 | 44.68 ms |
| Cold | Plugin MCP | 5/5 | 44.11 ms |
| Preflight | Private MCP | 5/5 | 34.81 ms |
| Preflight | Plugin MCP | 5/5 | 52.57 ms |

Every execution returned the seeded Scope ID and title. The observed native response contained 56 tools, including `list_scopes`, and completed before the first model request carrying a tool catalog. Five local successes per combination establish this bounded reference result; they do not resolve the independently reported missing-tool failure.

To repeat the same fixed matrix, preserve every run's output and temporary directory, including any failures:

```bash
minimax_matrix_status=0
for run in 1 2 3 4 5; do
  POWERCONTEXT_MINIMAX_ACCEPTANCE_COMMAND=/absolute/path/to/mcode \
    uv run python -m pytest tests/e2e/test_minimax_host.py \
    -k controlled_inference -q \
    --basetemp="/tmp/powercontext-minimax-acceptance-$run" \
    >"/tmp/powercontext-minimax-acceptance-$run.log" 2>&1 || minimax_matrix_status=1
done
test "$minimax_matrix_status" -eq 0
```

## Tool-discovery diagnostics

Once the inference fixture starts, each case saves `acceptance-evidence.json` under its pytest temporary directory, including on assertion failure. The native execution also receives `--diagnostics-dir` pointing to `native-diagnostics/` in that directory. Keep these files when reporting a failure. The evidence contains the selected route and startup mode, Server preflight metadata when performed, native MCP request methods/statuses/durations, response tool count and presence of `list_scopes`, model-visible tool names, selected tools, the Scope-result match verdict, and discovery errors. Native request start/response completion and model receipt timestamps use the same Python process's monotonic clock in milliseconds, so their order can be compared directly. Requests without a tool catalog can be provider-negotiation probes; the evidence marks whether the `tools` field was present. It excludes request headers, tool arguments, and tool results. A request still open when the evidence is written may have no final duration. MiniMax's own diagnostics record execution and tool progress separately. Failures during setup or Server preflight occur before inference and are reported by pytest directly.

Check the stages independently: Server MCP preflight, native `initialize` and `tools/list`, model-visible tool injection, then the authenticated `list_scopes` result. In the inspected official CLI 0.6.9 package, the connected-server log is emitted before fetching the tool inventory, so it does not establish tool availability.

The two routes use different discovery mechanisms. The configured private HTTP route has a default 2-second per-turn discovery budget. The plugin route uses its own MCP runtime with a default 15-second `tools/list` budget. It initially publishes cached capabilities and schedules discovery in the background; its readiness method waits for cached restoration and the directory watcher, without waiting for that background discovery. These paths are also visible in the host's [MCP service](https://github.com/MiniMax-AI/minimax-code/blob/da22f11c55d4748155d7162c1030414228a00565/packages/local-runtime-v2/src/service/mcp/runtime/local-mcp.service.ts), [plugin MCP runtime](https://github.com/MiniMax-AI/minimax-code/blob/da22f11c55d4748155d7162c1030414228a00565/packages/local-runtime-v2/src/service/plugin-system/mcp/runtime.ts), and [plugin readiness implementation](https://github.com/MiniMax-AI/minimax-code/blob/da22f11c55d4748155d7162c1030414228a00565/packages/local-runtime-v2/src/service/plugin-system/plugin-system.ts); the corresponding behavior was checked against the installed npm bundle. `mcode exec --timeout 40s` controls overall execution and does not make the first model request wait for plugin discovery. No supported public readiness barrier or discovery-budget override has been established for this CLI build.

A controlled experiment at `f4345d04` delayed only the successful `/mcp/` native `tools/list` response by 6 seconds, leaving the redirect and other MCP requests undelayed. The cold, plugin-only case failed its existing missing-tool assertion. The model received a catalog with 18 built-in tools and no PowerContext tools about 3.90 seconds after the request started. The Server then completed HTTP 200 in 6.04 seconds with 56 tools, including `list_scopes`. Thus the model used an incomplete catalog before the plugin discovery budget expired, even though the tools were returned successfully. The seeded Scope-result assertion remained unsatisfied. The zero-delay control with the same probe passed, exposing 74 tools (18 built-ins and 56 PowerContext tools) and returning the seeded Scope ID and title. A separate 11-second injected-delay run also failed with the inventory request still pending when evidence was saved.

This experiment demonstrates a plugin startup race under injected latency; it does not establish that the independently reported natural failure has the same cause. Increasing the overall execution timeout, using a separate-process Server preflight, or accepting an empty tool catalog would not establish correct cold-start behavior. Stable plugin-route qualification requires diagnostics from the affected environment, confirmation of the failed stage, and a cold plugin-only invocation returning the seeded Scope ID and title after the corresponding fix.

An isolated, unofficial readiness prototype waited for cached publication, active plugin discovery, and inventory publication before declaring the runtime ready. With the same injected-latency probe and unchanged assertions, both the 6-second and 11-second cold plugin-only cases returned the seeded Scope ID and title. A 16-second delay instead stopped startup with an explicit inventory-not-ready error and exit code 4, before any model request carrying a tool catalog. These results support a bounded discovery/publication barrier as a fix direction; they are not official CLI qualification. The prototype does not establish cancellation, hot-reload, or multi-server behavior, and the independent natural failure still requires evidence from its original environment.

A local source-level fix was also verified against public MiniMax commit `da22f11c55d4748155d7162c1030414228a00565` (source build version `0.6.5`). It waits during turn preparation for in-flight discovery and inventory publication, supports cancellation and a 20-second readiness-wait limit, and rechecks readiness at final capability capture after hot reload. Ten focused regressions and the full Linux capability gate passed (`5559 passed, 18 skipped`); PowerContext's full real-host suite passed all eleven cases. Under the same 11-second injected delay, the unmodified source build failed and the fixed source build returned the seeded Scope. A 16-second delay failed explicitly with native exit code 4 before any model tool catalog. This is an uncommitted local source change, separate from the unchanged official npm CLI 0.6.9; it does not close the independent failure or establish a released-host fix.

The package and connection checks use actual files, subprocesses, HTTP requests, and SQLite. Unit tests in `tests/test_cli_minimax.py` separately use simulated CLI output to cover parsing failures and installation recovery; those simulations are not native qualification.

## Limits

The plugin list reports resource counts rather than resource identities or an active MCP connection. CLI Server-info access is a separate HTTP probe; it does not establish a MiniMax MCP session. Desktop discovery, desktop refresh behavior, macOS, Windows, other CLI versions, and external model-provider calls require separate acceptance. Do not infer those capabilities from a successful Linux CLI run.
