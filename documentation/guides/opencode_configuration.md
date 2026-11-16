# OpenCode integration — prepared, not tested

OpenCode is not installed/discovered and no end-to-end task has succeeded. No integration or containment claim is made.

Prepared config: config/opencode.json. It selects only the local provider, uses http://127.0.0.1:11434/v1 and denies shell, external directories and network tools. Read/edit permissions are confined through tool policy and working directory; OpenCode permissions are not an OS security sandbox. Review current OpenCode version/schema and path behavior before enabling edits. Do not use --auto. Never connect a cloud provider for this experiment.

Launch from C:\workspace\local-agent-engine\test-repos\coding-baseline only, explicitly selecting ollama/qwen3.5:4b. Denying bash means trusted tests must initially run externally through the lab operator. Test recovery can be assessed by passing failing test output back to the same agent. For stronger containment use a dedicated restricted OS identity or VM after resource reassessment; do not grant unrestricted system access.

Success requires actual file edits, passing deterministic tests, a logged failed-test/recovery cycle, complete elapsed time and endpoint traffic evidence. None has been measured. Loopback configuration prevents selecting cloud inference in this config; it does not prove absence of all runtime telemetry/update traffic.

References: https://opencode.ai/docs/providers/ and https://opencode.ai/docs/permissions/
