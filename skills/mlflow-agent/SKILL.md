---
name: mlflow-agent
description: Route MLflow-related closed-network requests to tracing, evaluation, trace debugging, metrics, registration, or environment skills.
---

# MLflow Agent Dispatcher Skill

Use this skill when the user asks a broad MLflow question or wants help with MLflow setup, tracing, evaluation, model registration, metrics, or debugging but has not named a specific workflow.

## Routing

Map the user intent to the right local harness skill:

- ML Platform registration or model handoff -> `ml-registration`
- Training/job failure or dependency/path/resource error -> `ml-autofix`
- Closed-network Python, wheel, CUDA, or environment setup -> `offline-ml-env`
- Add or verify MLflow tracing -> `mlflow-tracing`
- Evaluate an LLM/agent workflow -> `mlflow-agent-evaluation`
- Analyze a trace, span, or failed run evidence -> `mlflow-trace-debug`
- Query usage, latency, token, quality, or run metrics -> `mlflow-metrics`
- vLLM/Qwen serving notes -> `vllm-ops-wiki`

## Process

1. Identify the user's immediate goal.
2. If multiple skills apply, use this order:
   - Environment setup
   - Tracing/observability
   - Registration/package creation
   - Evaluation
   - Debugging/Auto Fix
   - Metrics/reporting
3. Ask at most one clarifying question if the target workflow is unclear.
4. Prefer closed-network artifacts and local files over external calls.

## Closed-Network Rules

- Do not require external internet inside the closed network.
- Do not assume Databricks, Unity Catalog, or managed MLflow unless the user says they are available.
- Use internal MLflow Tracking/Registry URLs only when provided.
- Never write API keys, tokens, or service account secrets to reports.

## Output Pattern

```markdown
# MLflow 작업 라우팅

## 감지된 요청
- Intent:
- Selected Skill:
- Reason:

## 진행 순서
1.
2.
3.

## 필요한 입력
- Project Path:
- Tracking URI:
- Experiment:
- Log/Trace/Metric Target:
```
