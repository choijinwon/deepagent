---
name: vllm-ops-wiki
description: Write vLLM OpenAI-compatible serving notes and execution records in a wiki-style Markdown structure. Use when documenting vLLM model runs, base URLs, model names, tool-calling status, failures, or operational runbooks.
---

# vLLM Ops Wiki Skill

Use this skill when recording vLLM execution notes, model connection results, troubleshooting notes, or operational runbooks.

## Required Metadata

Always include:

- Model name
- Registered model list when available
- OpenAI-compatible base URL
- Chat completions path
- Tool Calling requirement
- Multi-agent status
- Internal tools used
- API Key recording status

Never record API keys or secrets.

## Wiki Page Template

```markdown
# vLLM 실행 기록

## vLLM Serving
- Model:
- Registered Models:
- OpenAI Compatible Base URL:
- Chat Completions Path: /chat/completions
- Tool Calling Required: yes
- API Key Stored: no

## DeepAgents Runtime
- Multi Agent:
- Harness Skills:
- Internal Tools:
- Subagents:

## Prompt

## Result

## Troubleshooting Notes
- Tool Calling 오류:
- 모델명 오류:
- Base URL 오류:
```

## Troubleshooting Guidance

- If a model fails tool calling, try another registered model and note the result.
- If `/v1/models` works but chat fails, verify `/v1/chat/completions`.
- If DeepAgents fails to call tools, verify the vLLM model's tool calling support.
