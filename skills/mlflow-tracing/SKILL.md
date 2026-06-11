---
name: mlflow-tracing
description: Add and verify MLflow tracing for Python AI agents, LangChain/LangGraph workflows, OpenAI-compatible calls, and internal LLM applications in a closed network.
---

# MLflow Tracing Skill

Use this skill when the user wants observability for an AI agent, LLM workflow, LangChain/LangGraph app, OpenAI-compatible API call, or internal vLLM/Qwen application.

## Reference Pattern

This skill is adapted from the public `mlflow/skills` tracing workflow:

- Detect the application framework.
- Add MLflow tracing at high-value boundaries.
- Verify that traces and spans are actually captured.
- Use trace evidence before evaluation or debugging.

## What To Trace

Trace high-value operations:

- Top-level request handlers and agent entrypoints.
- LLM chat/completions calls.
- Retrieval or document lookup.
- Tool/function calls.
- Planner/router decisions.
- External internal services such as DB/API/file storage.

Avoid noisy tracing:

- Simple string formatting.
- Small dict/list transformations.
- Pure validators.
- Environment loading.
- Logging helper functions.

## Closed-Network Setup

Check these first:

- `MLFLOW_TRACKING_URI`
- `MLFLOW_EXPERIMENT_NAME` or internal experiment naming rule
- Internal MLflow route, auth, and artifact path
- No secrets written to trace inputs/outputs
- Whether tracing is allowed for sensitive prompts or data

## Implementation Guidance

For Python projects:

```python
import mlflow

mlflow.set_tracking_uri("http://internal-mlflow")
mlflow.set_experiment("experiment-name")

with mlflow.start_run():
    mlflow.log_param("model", "qwen3.5")
    result = run_agent()
    mlflow.log_metric("success", 1)
```

For LLM/agent workflows, prefer trace boundaries around:

```text
run_agent()
call_llm()
retrieve_context()
call_tool()
write_artifact()
```

If the project already has MLflow setup, do not overwrite it. Add minimal instrumentation and preserve existing experiment configuration.

## Verification

Always verify after instrumentation:

```text
1. Run a minimal request.
2. Confirm an MLflow run or trace was created.
3. Confirm the trace has meaningful spans.
4. Confirm inputs/outputs do not leak secrets.
5. Save the verification result to Markdown.
```

## Required Output

```markdown
# MLflow Tracing 적용 결과

## 1. 감지된 앱 구조
- Framework:
- Entrypoint:
- LLM Provider:

## 2. 추가한 Trace 지점
- [ ] Agent entrypoint
- [ ] LLM call
- [ ] Tool call
- [ ] Retrieval

## 3. 검증 결과
- Tracking URI:
- Experiment:
- Run/Trace Created:
- Span Count:

## 4. 보안 확인
- Secrets Masked:
- Sensitive Inputs Excluded:
```
