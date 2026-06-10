---
name: access-audit
description: Analyze access-control review tasks for accounts, privileges, approvals, logs, and remediation actions. Use when the user asks about server access rights, account review, privilege audit, or permission inspection.
---

# Access Audit Skill

Use this skill for server access-right reviews, account audits, privilege checks, and permission inspection TODOs.

## Review Dimensions

Check these areas:

- Account owner and business purpose
- Privilege level and role mapping
- Approval evidence
- Last login and inactivity
- Shared or dormant accounts
- Administrator or root access
- Log collection and retention
- Revocation or remediation history

## Output Pattern

```markdown
# 접근권한 점검 체크리스트

## 계정/권한 확인
- [ ] 계정 목록 확보
- [ ] 권한 등급 확인
- [ ] 업무 필요성 확인

## 승인/증적 확인
- [ ] 권한 부여 승인 내역 확인
- [ ] 변경 이력 확인
- [ ] 예외 승인 여부 확인

## 로그/조치 확인
- [ ] 최근 로그인 확인
- [ ] 장기 미사용 계정 확인
- [ ] 회수 또는 권한 조정 대상 정리
```

## Guidance

- Flag missing evidence as "확인 필요".
- Do not assume compliance status without evidence.
- Keep recommendations actionable.
