---
name: offline-ml-env
description: Prepare and verify closed-network ML development environments, offline wheel bundles, Python versions, CUDA/runtime assumptions, and package compatibility.
---

# Offline ML Environment Skill

Use this skill when the user asks about closed-network ML setup, offline package installation, Python environment compatibility, wheel bundles, CUDA/runtime issues, or Windows 11 Pro deployment.

## Closed-Network Rules

- External downloads happen only on an internet-connected external PC.
- Closed-network PCs install only from copied source and wheel folders.
- Keep Python version, OS, architecture, CUDA/runtime assumptions, and package versions aligned between external and closed-network PCs.
- Do not place secrets in logs, reports, wiki pages, or package manifests.

## Environment Flow

```text
1. Confirm target OS and Python version.
2. Build offline wheel bundle on external PC.
3. Copy source + wheels + manifest to closed-network PC.
4. Create virtual environment.
5. Install with `pip --no-index --find-links`.
6. Run import checks.
7. Run platform doctor.
8. Verify MLflow, model API, and internal paths.
9. Save environment report.
```

## Required Checks

Always check:

- Windows version and PowerShell execution policy.
- Python version and architecture.
- Virtual environment activation.
- `requirements.txt` and lock file source.
- Wheel availability for heavy ML packages.
- `pip install --no-index --find-links=...`.
- `deepagent-doctor` result.
- `MLFLOW_TRACKING_URI`.
- `QWEN_BASE_URL`, `QWEN_MODEL`, and tool-calling capability when using agents.
- Internal dataset/artifact mount paths.
- CUDA/GPU runtime compatibility when GPU training is required.

## Compatibility Warnings

Flag these as `[주의]` or `[오류]`:

- External PC Python version differs from closed-network PC.
- `requirements.txt` contains `git+`, `http://`, `https://`, or direct online install assumptions.
- Conda-only environment without a pip/wheel conversion plan.
- Missing wheel for package with native extension.
- CUDA package version does not match the platform image/runtime.
- Notebook-only project without script conversion or papermill plan.
- API key, token, or internal IP appears in saved logs.

## Required Output

````markdown
# 폐쇄망 ML 환경 점검 결과

## 1. 환경 요약
- OS:
- Python:
- Virtualenv:
- Offline Package Dir:
- Platform Image:

## 2. 설치/검증 체크리스트
- [ ] wheel bundle 생성
- [ ] bundle manifest 확인
- [ ] venv 생성
- [ ] offline install 실행
- [ ] import check 실행
- [ ] doctor 실행

## 3. 위험 항목
- [주의]
- [오류]

## 4. 다음 명령
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install --no-index --find-links=..\offline_packages -r requirements.txt
deepagent-doctor
```
````

## Quality Checklist

- Prefer commands that work on Windows 11 Pro PowerShell.
- Keep instructions copy-pasteable.
- Mention whether the command runs on the external PC or closed-network PC.
- Do not recommend internet access inside the closed network.
