---
name: ml-autofix
description: Analyze ML training, platform job, MLflow, dependency, path, GPU memory, and resource scheduling errors and produce safe closed-network fix plans.
---

# ML Auto Fix Skill

Use this skill when a training job, registration job, MLflow run, dependency install, or platform execution fails and the user provides logs or error text.

## Closed-Network Rules

- Do not suggest internet downloads inside the closed network.
- If a missing dependency is found, suggest adding it to `requirements.lock.txt` or rebuilding the offline wheel bundle on the external PC.
- Do not rewrite source files automatically unless the user explicitly approves.
- Prefer fix plans, patch candidates, and retest commands.
- Keep original project files unchanged when a wrapper or registration workspace can solve the issue.

## Error Categories

Classify logs into these categories:

- `missing_package`: `ModuleNotFoundError`, `ImportError`, missing wheel.
- `missing_file`: `FileNotFoundError`, config path, dataset path, working directory mismatch.
- `mlflow_config`: tracking URI, experiment, registry URI, auth, connectivity, artifact path.
- `gpu_memory`: CUDA out of memory, batch size too large, model too large.
- `resource_scheduling`: pending job, queue/quota/resource unavailable.
- `image_runtime`: missing Python, CUDA mismatch, wrong container image, missing system library.
- `permission`: dataset, artifact, registry, service account, file share permission.
- `entrypoint_args`: wrong script, missing required CLI arg, wrong config argument.
- `unknown`: no known pattern matched.

## Analysis Flow

Follow this order:

```text
1. Identify failing command or job name.
2. Extract first error, root cause hint, and final traceback.
3. Classify category and severity.
4. Identify likely file/config to change.
5. Propose smallest safe fix.
6. Provide retest command.
7. Note whether offline package bundle must be rebuilt.
```

## Fix Guidance

Use these default recommendations:

- Missing package: add package to requirements, rebuild offline bundle externally, reinstall with `--no-index`.
- Missing file: verify working directory, mounted path, dataset path, config path, and job args.
- MLflow failure: verify `MLFLOW_TRACKING_URI`, experiment name, registry URI, service account, and internal route.
- CUDA OOM: reduce batch size, gradient accumulation, mixed precision, gradient checkpointing, or request larger GPU/memory.
- Resource scheduling: check queue, quota, CPU/GPU/memory request, and pending events.
- Image/runtime: check Python/CUDA/library versions and platform image.

## Required Output

````markdown
# ML Auto Fix Plan

## 1. 실패 요약
- Command/Job:
- Exit Code:
- Category:
- Severity:

## 2. 증거
```text
핵심 로그 5~20줄
```

## 3. 원인 추정
- Primary Cause:
- Related Files:

## 4. 수정 후보
- [ ] 수정 대상:
- [ ] 변경 내용:
- [ ] 오프라인 번들 재생성 필요 여부:

## 5. 재검증 명령
```powershell
python entrypoint.py
```

## 6. 플랫폼팀 문의가 필요한 경우
- Queue/quota:
- 권한:
- 내부 API/Registry:
````

## Patch Policy

- Patch candidates may be created for requirements additions, wrapper argument changes, or generated registration workspace files.
- Ask for explicit approval before applying a patch.
- After applying a patch, rerun the same command and save the new log.
