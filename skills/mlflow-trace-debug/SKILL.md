---
name: mlflow-trace-debug
description: Analyze MLflow traces, spans, failed runs, chat sessions, and tool-call evidence to find root causes and recommend fixes.
---

# MLflow Trace Debug Skill

Use this skill when the user provides an MLflow trace ID, run ID, exported trace JSON/CSV, chat session log, or failed agent execution record.

## Debugging Flow

```text
1. Identify the trace/run/session.
2. Reconstruct the execution timeline.
3. Locate the first failing span or abnormal output.
4. Correlate failure with code, prompt, tool, model, or environment.
5. Classify root cause.
6. Propose minimal fix and retest.
```

## What To Inspect

- Span tree and parent/child order.
- Latency outliers.
- Error status and exception text.
- LLM prompt/response boundaries.
- Tool call arguments and outputs.
- Retrieval result count and relevance.
- Token usage or truncation.
- Model name, endpoint, and timeout.
- User/session metadata.

## Root Cause Categories

- Prompt issue
- Tool selection issue
- Tool runtime failure
- Retrieval/data issue
- Model endpoint issue
- Context length/truncation
- Auth/permission issue
- MLflow tracking/config issue
- Unknown

## Closed-Network Rules

- Do not fetch traces from external MLflow servers.
- If the trace is not accessible, ask the user to export the trace/run/session as JSON, CSV, or Markdown.
- Mask secrets, tokens, internal IPs, and dataset identifiers in reports.

## Required Output

```markdown
# MLflow Trace Debug Report

## 1. 대상
- Trace/Run/Session:
- Model:
- Endpoint:

## 2. 실행 타임라인
| Step | Span/Action | Status | Evidence |
|---|---|---|---|

## 3. 원인 분석
- First Failure:
- Root Cause:
- Category:

## 4. 수정 제안
- Code:
- Prompt:
- Tool:
- Environment:

## 5. 재검증
- Command:
- Expected Evidence:
```

## Quality Checklist

- Focus on the first meaningful failure, not only the final exception.
- Use evidence from spans/logs.
- Distinguish model quality issues from infrastructure failures.
- Provide a retest command or verification evidence.
