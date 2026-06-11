---
name: ml-registration
description: Guide AI and ML developers through closed-network AI Studio registration, including project scan, MLflow setup, job template review, readiness checks, package creation, and handoff.
---

# AI Studio Registration Skill

Use this skill when the user wants to register an AI/ML project to AI Studio, create registration artifacts, prepare a Job Template, configure MLflow, or help a junior developer follow the registration flow without reading a long manual.

## Reference Principles

This skill follows public MLflow and Kubernetes platform patterns, adapted for closed-network internal use:

- MLflow Tracking records runs, parameters, metrics, code context, and artifacts for later review.
- MLflow Experiments group related runs and models for a task.
- MLflow Model Registry manages registered models, model versions, aliases, tags, descriptions, and lineage.
- Platform jobs should declare execution command, image, queue, CPU, GPU, memory, environment variables, and artifact/log outputs.
- Internal platform specifics always override this skill when a local manual or schema is provided.

## Closed-Network Rules

- Do not use external internet, external package indexes, external APIs, or external SaaS tools.
- Do not assume the internal AI Studio API schema unless it is provided.
- Generate offline artifacts first: profile, report, config, job template, wrapper, requirements lock, and package zip.
- Treat API keys, tokens, internal IPs, hostnames, dataset paths, and service account names as sensitive.

## Registration Flow

Follow this order:

```text
1. Project Intake
2. Project Type Detection
3. Entrypoint Confirmation
4. Environment Analysis
5. MLflow Configuration
6. Job Template Draft
7. Resource Recommendation
8. Registration Readiness Check
9. Registration Package Creation
10. Job Execution and Log Review
11. Model Registry Handoff
```

## Required Checks

Always check:

- Project path exists and is the intended project root.
- Framework type: PyTorch, TensorFlow/Keras, XGBoost, Scikit-learn, HuggingFace, Notebook, or Legacy script.
- Entrypoint: `train.py`, `main.py`, `run.py`, notebook, or explicit script path.
- Environment files: `requirements.txt`, `pyproject.toml`, `environment.yml`, lock files, Dockerfile.
- External dependency risks: `git+`, `http://`, `https://`, direct `pip install`, local absolute paths.
- MLflow Tracking URI and experiment name.
- Job queue, image, CPU, GPU, memory, command, arguments, working directory.
- Dataset path, config path, model output path, artifact path.
- Registration readiness score and unresolved warnings.

## Junior-Friendly Wizard Behavior

When information is missing, ask one question at a time:

```text
1. 등록할 ML 프로젝트 폴더는 어디인가요?
2. 학습 진입점은 이 파일이 맞나요?
3. 데이터 경로 인자는 무엇인가요?
4. config 파일 경로가 있나요?
5. 모델 출력 경로는 어디인가요?
6. MLflow Tracking URI는 무엇인가요?
7. 사용할 AI Studio Queue는 무엇인가요?
8. GPU가 꼭 필요한가요?
9. CPU/GPU/Memory 기본 추천값을 그대로 사용할까요?
10. 등록 패키지를 생성할까요?
```

## Required Output

Use this structure for registration guidance:

```markdown
# AI Studio 등록 준비 결과

## 1. 자동 분석 요약
- Project Type:
- Primary Framework:
- Entrypoint:
- Environment Files:
- Readiness:

## 2. 등록 전 점검표
- [ ] 학습 진입점 확인
- [ ] 환경 파일 확인
- [ ] MLflow Tracking URI 확인
- [ ] AI Studio Queue 확인
- [ ] CPU/GPU/Memory 확인
- [ ] 실행 Arguments 확인
- [ ] 외부 의존성 위험 확인

## 3. 생성 산출물
- `registration_profile.json`
- `registration_report.md`
- `mlflow_config.yaml`
- `job_template.yaml`
- `entrypoint.py`
- `requirements.lock.txt`
- `registration_package.zip`

## 4. 다음 단계
- 등록 패키지 전달:
- Job 실행:
- 오류 로그 분석:
- Model Registry 등록:
```

## Quality Checklist

- Explain the next action, not just the finding.
- Separate `[OK]`, `[주의]`, and `[오류]`.
- Prefer a readiness score and checklist over long prose.
- Never claim the model is registered unless an actual platform API call or registry evidence is provided.
