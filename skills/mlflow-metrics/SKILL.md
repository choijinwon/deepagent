---
name: mlflow-metrics
description: Query and summarize MLflow run, trace, model, latency, token, cost, and quality metrics for closed-network reporting.
---

# MLflow Metrics Skill

Use this skill when the user asks for MLflow metrics, usage trends, quality reports, run comparisons, model comparison, latency analysis, token usage, or registration readiness reporting.

## Closed-Network Rules

- Query only internal MLflow servers or local exported files.
- If MLflow API access is unavailable, work from provided CSV/JSON/Markdown exports.
- Do not expose secrets or internal service identifiers in final reports.
- Use aggregate summaries by default.

## Metrics To Collect

- Run count by experiment.
- Success/failure count.
- Latency average, p50, p95, max.
- Token usage by model, route, or user group.
- Error rate by category.
- Tool-call success rate.
- Evaluation scorer pass rate.
- Model version and alias status.
- Registration readiness trend.

## Analysis Flow

```text
1. Confirm experiment/run/model scope.
2. Confirm time range.
3. Collect metrics from MLflow or exported files.
4. Normalize by model, task, queue, or project.
5. Identify anomalies.
6. Produce operational summary and actions.
```

## Report Pattern

```markdown
# MLflow Metrics Report

## 1. Scope
- Experiment:
- Time Range:
- Models:
- Data Source:

## 2. Summary
- Runs:
- Success Rate:
- Error Rate:
- Latency p95:
- Token Usage:

## 3. Findings
- [주의]
- [오류]
- [개선]

## 4. Recommended Actions
- Cost:
- Latency:
- Quality:
- Reliability:
```

## Junior-Friendly Guidance

If the user is not sure what to query, suggest:

- "최근 7일 실험별 실패율"
- "모델별 평균 latency와 p95"
- "Job Template별 OOM 발생 건수"
- "등록 준비 점수 80점 미만 프로젝트 목록"
- "평가 scorer별 pass rate"
