---
name: security-report
description: Create closed-network security inspection reports, TODO lists, and executive-ready summaries. Use when the user asks for a security report, inspection draft, audit note, checklist, TODO, or remediation summary.
---

# Security Report Skill

Use this skill when the user asks for a security inspection report, TODO, checklist, audit memo, remediation summary, or internal review draft.

## Closed Network Rules

- Do not use external internet, external APIs, web search, or SaaS tools.
- Use only registered internal tools, provided prompt content, and internal data explicitly supplied by the user.
- If evidence is missing, write it as an item to verify instead of inventing details.

## Required Output

Use this structure unless the user asks for another format:

```markdown
# 보안 점검 보고서 초안

## 1. 점검 개요
- 점검 대상:
- 점검 목적:
- 점검 범위:

## 2. 주요 TODO
- [ ] 점검 대상 시스템 확인
- [ ] 접근 권한 현황 확인
- [ ] 로그 수집 여부 확인
- [ ] 취약점 조치 이력 확인
- [ ] 담당자 확인
- [ ] 최종 보고서 작성

## 3. 확인 필요 사항
- 확인 필요:

## 4. 후속 조치
- 담당:
- 기한:
- 산출물:
```

## Quality Checklist

- Keep the result practical and ready for an internal worker to use.
- Separate confirmed facts from items that need verification.
- Prefer checklist and table-like structure over long prose.
- Mention that external web tools were not used when relevant.
