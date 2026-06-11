---
name: mlflow-agent-evaluation
description: Plan and run closed-network MLflow evaluation for AI agents with datasets, scorers, tracing prerequisites, dry runs, and result reports.
---

# MLflow Agent Evaluation Skill

Use this skill when evaluating an internal AI agent, chatbot, RAG workflow, tool-using agent, or model-routing workflow.

## Reference Pattern

This skill follows the public `mlflow/skills` evaluation pattern:

- Tracing must work before evaluation.
- Understand the agent purpose before picking metrics.
- Discover or define datasets.
- Run a tiny dry run before a full evaluation.
- Analyze results and produce improvement actions.

## Closed-Network Rules

- Do not call external evaluator APIs unless the internal environment explicitly provides them.
- Prefer internal Qwen/vLLM/gamma/gpt20 judge models if judge scoring is needed.
- If no judge model is available, use rule-based/manual scorers and record the limitation.
- Do not create large synthetic datasets without user approval.
- Keep evaluation records free of secrets and sensitive raw data.

## Evaluation Flow

```text
1. Confirm agent purpose.
2. Confirm 2-3 critical quality criteria.
3. Confirm tracing is enabled and verified.
4. Find existing evaluation data.
5. Create or select a small sanity dataset.
6. Define scorers.
7. Run a 3-case dry run.
8. Run full evaluation.
9. Analyze failures.
10. Generate improvement plan.
```

## Required Questions

Ask these before evaluation:

- What does the agent do?
- What are the 2-3 things it must get right?
- What failure modes have already been observed?
- Is there an existing evaluation dataset or production log sample?
- Which model should be used as the judge, if any?

## Scorer Guidance

Common scorers:

- Correctness
- Relevance
- Completeness
- Groundedness
- Tool selection accuracy
- Safety/compliance
- Latency
- Cost/token usage

Use clear outputs such as `yes/no`, numeric scores, or structured labels. Avoid ambiguous values that cannot be aggregated.

## Dry Run Gate

Before a full evaluation:

```text
Run 3 cases only.
Stop if:
- responses are empty
- tools fail
- judge/scorer returns invalid values
- MLflow run/trace is missing
- internal model endpoint is unavailable
```

## Required Output

```markdown
# Agent Evaluation Plan

## 1. Agent Purpose
- Purpose:
- Critical Behaviors:
- Known Failures:

## 2. Dataset
- Existing Dataset:
- Sanity Dataset:
- Full Dataset Size:

## 3. Scorers
- Correctness:
- Relevance:
- Tool Accuracy:
- Safety:

## 4. Dry Run Result
- Cases:
- Passed:
- Blockers:

## 5. Full Evaluation Result
- Pass Rate:
- Top Failure Types:
- Recommended Fixes:
```
