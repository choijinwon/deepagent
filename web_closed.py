import json
import os
import re
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from autofix_common import analyze_log_file, render_fix_report, save_fix_report
from dev_common import generate_patch_candidates, render_patch_candidates, save_patch_candidates
from ml_common import ensure_model_catalog, save_experiment, save_model_catalog_markdown
from ops_common import goal_to_markdown, save_goal_markdown, session_dir, slugify as common_slugify
from registration_common import (
    create_registration_package,
    render_registration_report,
    save_registration_profile,
    scan_project,
    scaffold_registered_workspace,
)
from scaffold_common import (
    SCAFFOLD_SAMPLE,
    apply_scaffold,
    parse_scaffold_text,
    render_scaffold_summary,
    scaffold_to_context_files,
)
from app_closed import (
    build_alternate_agent_request,
    build_agent_request,
    build_agent,
    get_available_models,
    get_default_model,
    get_harness_skill_files,
    get_harness_skill_names,
    harness_skills_enabled,
    invoke_agent_compatible,
    is_message_format_error,
)
from dotenv import load_dotenv


load_dotenv()

HOST = os.getenv("WEB_HOST", "127.0.0.1")
PORT = int(os.getenv("WEB_PORT", "8000"))
DEFAULT_MODEL = get_default_model()
MODEL_OPTIONS = get_available_models()
PROMPT_STORE_PATH = Path(os.getenv("PROMPT_STORE_PATH", "prompt_templates.json"))
WIKI_LOG_DIR = Path(os.getenv("WIKI_LOG_DIR", "wiki_logs"))
WIKI_LOG_STYLE = os.getenv("WIKI_LOG_STYLE", "vllm")
PLAN_DIR = Path(os.getenv("PLAN_DIR", "plans"))
WORKSPACE_DIR = Path(os.getenv("CHAT_WORKSPACE_DIR", "agent_workspace"))
MASK_SENSITIVE_LOGS = os.getenv("MASK_SENSITIVE_LOGS", "true").lower() in ("1", "true", "yes", "y")
try:
    STREAM_CHUNK_CHARS = max(400, int(os.getenv("STREAM_CHUNK_CHARS", "1800")))
except ValueError:
    STREAM_CHUNK_CHARS = 1800

HTML = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>폐쇄망 DeepAgents Qwen 3.5 PoC</title>
  <style>
    :root {
      color-scheme: light;
      font-family: "Segoe UI", "Malgun Gothic", Arial, sans-serif;
      background: #f5f7fb;
      color: #172033;
    }
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
    }
    main {
      width: min(1180px, calc(100vw - 32px));
      background: #ffffff;
      border: 1px solid #dce3ef;
      border-radius: 8px;
      box-shadow: 0 20px 60px rgba(20, 32, 54, 0.12);
      overflow: hidden;
    }
    header {
      padding: 22px 24px;
      border-bottom: 1px solid #e6ebf3;
      background: #102033;
      color: white;
    }
    h1 {
      margin: 0;
      font-size: 21px;
      font-weight: 700;
    }
    .subtitle {
      margin-top: 7px;
      color: #c8d4e5;
      font-size: 14px;
    }
    section {
      padding: 22px 24px;
    }
    label {
      display: block;
      margin-bottom: 8px;
      font-weight: 700;
    }
    textarea {
      width: 100%;
      min-height: 140px;
      box-sizing: border-box;
      padding: 14px;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      resize: vertical;
      font: inherit;
      line-height: 1.5;
    }
    .controls {
      display: grid;
      grid-template-columns: minmax(180px, 260px) 1fr;
      gap: 14px;
      align-items: end;
      margin-bottom: 14px;
    }
    select {
      width: 100%;
      box-sizing: border-box;
      padding: 10px 12px;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      background: #ffffff;
      font: inherit;
    }
    input[type="text"] {
      width: 100%;
      box-sizing: border-box;
      padding: 10px 12px;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      background: #ffffff;
      font: inherit;
    }
    .prompt-library {
      display: grid;
      grid-template-columns: minmax(180px, 260px) 1fr;
      gap: 14px;
      margin-bottom: 14px;
    }
    .ops-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
      margin: 14px 0;
    }
    .ops-panel {
      border: 1px solid #dce3ef;
      border-radius: 6px;
      padding: 14px;
      background: #f8fafc;
    }
    .ops-panel textarea {
      min-height: 86px;
      background: #ffffff;
    }
    .scaffold-panel {
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      padding: 14px;
      margin: 14px 0;
      background: #f8fafc;
    }
    #scaffoldText {
      min-height: 230px;
      background: #ffffff;
      font-family: "Cascadia Mono", Consolas, monospace;
      font-size: 13px;
    }
    .toggle {
      display: flex;
      align-items: center;
      gap: 8px;
      min-height: 41px;
      font-weight: 700;
    }
    .toggle input {
      width: 18px;
      height: 18px;
    }
    .actions {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 12px;
      margin-top: 12px;
    }
    button {
      border: 0;
      border-radius: 6px;
      padding: 11px 16px;
      background: #1769e0;
      color: white;
      font-weight: 700;
      cursor: pointer;
    }
    button:disabled {
      cursor: wait;
      background: #8baee0;
    }
    button.secondary {
      background: #40516b;
    }
    button.ghost {
      background: #e8eef7;
      color: #172033;
    }
    .status {
      color: #526173;
      font-size: 14px;
    }
    .result-view {
      min-height: 180px;
      margin: 18px 0 0;
      padding: 16px;
      overflow: auto;
      border: 1px solid #dce3ef;
      border-radius: 6px;
      background: #ffffff;
      color: #172033;
      line-height: 1.6;
      font-size: 14px;
    }
    .result-view > *:first-child {
      margin-top: 0;
    }
    .result-view > *:last-child {
      margin-bottom: 0;
    }
    .result-view h1,
    .result-view h2,
    .result-view h3 {
      margin: 18px 0 10px;
      line-height: 1.25;
      color: #102033;
    }
    .result-view h1 {
      padding-bottom: 8px;
      border-bottom: 1px solid #dce3ef;
      font-size: 22px;
    }
    .result-view h2 {
      font-size: 18px;
    }
    .result-view h3 {
      font-size: 16px;
    }
    .result-view p {
      margin: 9px 0;
    }
    .result-view ul,
    .result-view ol {
      margin: 8px 0 12px 22px;
      padding: 0;
    }
    .result-view li {
      margin: 4px 0;
      padding-left: 2px;
    }
    .result-view blockquote {
      margin: 12px 0;
      padding: 8px 12px;
      border-left: 4px solid #7aa7e8;
      background: #f3f7fd;
      color: #344154;
    }
    .result-view code {
      padding: 2px 5px;
      border-radius: 4px;
      background: #eef3f8;
      font-family: "Cascadia Mono", Consolas, monospace;
      font-size: 0.92em;
    }
    .result-view pre {
      margin: 12px 0;
      padding: 13px;
      overflow-x: auto;
      white-space: pre;
      border: 1px solid #d6deea;
      border-radius: 6px;
      background: #101827;
      color: #f6f8fb;
      font-family: "Cascadia Mono", Consolas, monospace;
      font-size: 13px;
      line-height: 1.55;
    }
    .result-view pre code {
      padding: 0;
      background: transparent;
      color: inherit;
      font-size: inherit;
    }
    .result-view table {
      width: 100%;
      margin: 12px 0;
      border-collapse: collapse;
      display: block;
      overflow-x: auto;
      border: 1px solid #dce3ef;
      border-radius: 6px;
    }
    .result-view th,
    .result-view td {
      padding: 9px 10px;
      border-bottom: 1px solid #e6ebf3;
      border-right: 1px solid #e6ebf3;
      text-align: left;
      vertical-align: top;
      min-width: 120px;
    }
    .result-view th {
      background: #f1f5fb;
      color: #102033;
      font-weight: 700;
    }
    .result-view tr:last-child td {
      border-bottom: 0;
    }
    .result-view .task-checkbox {
      margin-right: 7px;
      transform: translateY(1px);
    }
    .result-view .empty-result {
      color: #718096;
    }
    @media (max-width: 680px) {
      .controls,
      .prompt-library,
      .ops-grid {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>폐쇄망 DeepAgents Qwen 3.5 PoC</h1>
      <div class="subtitle">외부 검색 없이 내부 Qwen 3.5 API와 등록된 사내 Tool만 사용합니다.</div>
    </header>
    <section>
      <div class="controls">
        <div>
          <label for="model">모델 선택</label>
          <select id="model"></select>
        </div>
        <label class="toggle" for="multiAgent">
          <input id="multiAgent" type="checkbox" checked>
          멀티에이전트 사용
        </label>
      </div>
      <div class="prompt-library">
        <div>
          <label for="savedPrompts">저장된 프롬프트</label>
          <select id="savedPrompts"></select>
        </div>
        <div>
          <label for="promptName">프롬프트 이름</label>
          <input id="promptName" type="text" placeholder="예: 접근권한 점검 보고서">
        </div>
      </div>
      <div class="prompt-library">
        <div>
          <label for="promptCategory">프롬프트 분류</label>
          <input id="promptCategory" type="text" placeholder="예: 보안점검">
        </div>
        <div>
          <label for="promptTags">태그</label>
          <input id="promptTags" type="text" placeholder="예: 접근권한, vllm, 보고서">
        </div>
      </div>
      <label for="prompt">요청 내용</label>
      <textarea id="prompt">서버 접근권한 보안 점검 TODO 만들어줘.</textarea>
      <div class="scaffold-panel">
        <label for="scaffoldText">작업 생성기</label>
        <textarea id="scaffoldText" placeholder="# Goal, # Plan, # Folders, # Files 형식으로 붙여넣으면 폴더와 파일을 자동 생성합니다."></textarea>
        <div class="actions">
          <button id="sampleScaffold" class="ghost" type="button">예시 넣기</button>
          <button id="previewScaffold" class="secondary" type="button">미리보기</button>
          <button id="applyScaffold" class="secondary" type="button">자동 생성</button>
          <button id="runScaffold" type="button">생성 후 실행</button>
          <button id="catalog" class="ghost" type="button">모델 카탈로그</button>
          <button id="experiment" class="ghost" type="button">모델 비교 실험</button>
        </div>
      </div>
      <div class="scaffold-panel">
        <label for="registerPath">AI Studio 등록 대상 프로젝트 경로</label>
        <input id="registerPath" type="text" placeholder="예: C:\\work\\my-model 또는 /workspace/my-model">
        <label for="registerLogPath">오류 로그 파일 경로</label>
        <input id="registerLogPath" type="text" placeholder="예: agent_workspace/logs/job-error.log">
        <div class="actions">
          <button id="registerScan" class="secondary" type="button">등록 분석</button>
          <button id="registerScaffold" class="secondary" type="button">등록 구조 생성</button>
          <button id="registerPackage" class="secondary" type="button">등록 패키지 생성</button>
          <button id="registerFixLog" class="ghost" type="button">오류 로그 분석</button>
        </div>
      </div>
      <div class="ops-grid">
        <div class="ops-panel">
          <label for="goalTitle">목표</label>
          <input id="goalTitle" type="text" placeholder="예: 폐쇄망 DeepAgents PoC 검증">
          <label for="goalCriteria">성공 기준</label>
          <textarea id="goalCriteria" placeholder="한 줄에 하나씩 입력"></textarea>
          <label for="goalConstraints">제약사항</label>
          <textarea id="goalConstraints" placeholder="예: 외부 인터넷 사용 금지"></textarea>
        </div>
        <div class="ops-panel">
          <label for="planTitle">플랜</label>
          <input id="planTitle" type="text" placeholder="예: 보안 점검 보고서 작성">
          <label for="planSteps">플랜 단계</label>
          <textarea id="planSteps" placeholder="한 줄에 하나씩 입력"></textarea>
          <label for="attachPath">첨부 파일 경로</label>
          <input id="attachPath" type="text" placeholder="agent_workspace 안의 파일 경로">
        </div>
      </div>
      <div class="actions">
        <button id="run" type="button">실행</button>
        <button id="test" class="secondary" type="button">모델 연결 테스트</button>
        <button id="savePrompt" class="secondary" type="button">프롬프트 저장</button>
        <button id="saveGoal" class="secondary" type="button">목표 저장</button>
        <button id="savePlan" class="secondary" type="button">플랜 저장</button>
        <button id="deletePrompt" class="ghost" type="button">프롬프트 삭제</button>
        <button id="download" class="ghost" type="button">결과 다운로드</button>
        <span id="status" class="status">대기 중</span>
      </div>
      <div id="result" class="result-view">결과가 여기에 표시됩니다.</div>
    </section>
  </main>
  <script>
    const button = document.getElementById("run");
    const testButton = document.getElementById("test");
    const savePromptButton = document.getElementById("savePrompt");
    const saveGoalButton = document.getElementById("saveGoal");
    const savePlanButton = document.getElementById("savePlan");
    const sampleScaffoldButton = document.getElementById("sampleScaffold");
    const previewScaffoldButton = document.getElementById("previewScaffold");
    const applyScaffoldButton = document.getElementById("applyScaffold");
    const runScaffoldButton = document.getElementById("runScaffold");
    const catalogButton = document.getElementById("catalog");
    const experimentButton = document.getElementById("experiment");
    const registerScanButton = document.getElementById("registerScan");
    const registerScaffoldButton = document.getElementById("registerScaffold");
    const registerPackageButton = document.getElementById("registerPackage");
    const registerFixLogButton = document.getElementById("registerFixLog");
    const deletePromptButton = document.getElementById("deletePrompt");
    const downloadButton = document.getElementById("download");
    const statusText = document.getElementById("status");
    const promptInput = document.getElementById("prompt");
    const modelSelect = document.getElementById("model");
    const multiAgent = document.getElementById("multiAgent");
    const savedPrompts = document.getElementById("savedPrompts");
    const promptName = document.getElementById("promptName");
    const promptCategory = document.getElementById("promptCategory");
    const promptTags = document.getElementById("promptTags");
    const result = document.getElementById("result");
    const goalTitle = document.getElementById("goalTitle");
    const goalCriteria = document.getElementById("goalCriteria");
    const goalConstraints = document.getElementById("goalConstraints");
    const planTitle = document.getElementById("planTitle");
    const planSteps = document.getElementById("planSteps");
    const attachPath = document.getElementById("attachPath");
    const scaffoldText = document.getElementById("scaffoldText");
    const registerPath = document.getElementById("registerPath");
    const registerLogPath = document.getElementById("registerLogPath");
    let rawResultText = "결과가 여기에 표시됩니다.";

    function lineList(value) {
      return value.split("\\n").map((item) => item.trim()).filter(Boolean);
    }

    function escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }

    function renderInlineMarkdown(value) {
      let html = escapeHtml(value);
      html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
      html = html.replace(/\\*\\*([^*]+)\\*\\*/g, "<strong>$1</strong>");
      html = html.replace(/\\[([^\\]]+)\\]\\(([^)\\s]+)\\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
      return html;
    }

    function isTableSeparator(line) {
      return /^\\s*\\|?\\s*:?-{3,}:?\\s*(\\|\\s*:?-{3,}:?\\s*)+\\|?\\s*$/.test(line);
    }

    function splitTableRow(line) {
      let text = line.trim();
      if (text.startsWith("|")) {
        text = text.slice(1);
      }
      if (text.endsWith("|")) {
        text = text.slice(0, -1);
      }
      return text.split("|").map((cell) => cell.trim());
    }

    function flushParagraph(parts, html) {
      if (parts.length) {
        html.push(`<p>${renderInlineMarkdown(parts.join(" "))}</p>`);
        parts.length = 0;
      }
    }

    function renderMarkdown(markdown) {
      const text = String(markdown || "").trimEnd();
      if (!text.trim()) {
        return '<p class="empty-result">결과가 여기에 표시됩니다.</p>';
      }

      const lines = text.split("\\n");
      const html = [];
      const paragraph = [];
      let listType = "";
      let listOpen = false;
      let inCode = false;
      let codeLines = [];

      function closeList() {
        if (listOpen) {
          html.push(`</${listType}>`);
          listOpen = false;
          listType = "";
        }
      }

      function openList(type) {
        if (!listOpen || listType !== type) {
          closeList();
          listType = type;
          listOpen = true;
          html.push(`<${type}>`);
        }
      }

      for (let index = 0; index < lines.length; index += 1) {
        const line = lines[index];
        const trimmed = line.trim();

        if (trimmed.startsWith("```")) {
          if (inCode) {
            html.push(`<pre><code>${escapeHtml(codeLines.join("\\n"))}</code></pre>`);
            codeLines = [];
            inCode = false;
          } else {
            flushParagraph(paragraph, html);
            closeList();
            inCode = true;
          }
          continue;
        }
        if (inCode) {
          codeLines.push(line);
          continue;
        }

        if (!trimmed) {
          flushParagraph(paragraph, html);
          closeList();
          continue;
        }

        if (line.includes("|") && index + 1 < lines.length && isTableSeparator(lines[index + 1])) {
          flushParagraph(paragraph, html);
          closeList();
          const headers = splitTableRow(line);
          index += 2;
          const rows = [];
          while (index < lines.length && lines[index].includes("|") && lines[index].trim()) {
            rows.push(splitTableRow(lines[index]));
            index += 1;
          }
          index -= 1;
          html.push("<table><thead><tr>");
          for (const header of headers) {
            html.push(`<th>${renderInlineMarkdown(header)}</th>`);
          }
          html.push("</tr></thead><tbody>");
          for (const row of rows) {
            html.push("<tr>");
            for (let cellIndex = 0; cellIndex < headers.length; cellIndex += 1) {
              html.push(`<td>${renderInlineMarkdown(row[cellIndex] || "")}</td>`);
            }
            html.push("</tr>");
          }
          html.push("</tbody></table>");
          continue;
        }

        const heading = /^(#{1,3})\\s+(.+)$/.exec(trimmed);
        if (heading) {
          flushParagraph(paragraph, html);
          closeList();
          const level = heading[1].length;
          html.push(`<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`);
          continue;
        }

        const quote = /^>\\s?(.+)$/.exec(trimmed);
        if (quote) {
          flushParagraph(paragraph, html);
          closeList();
          html.push(`<blockquote>${renderInlineMarkdown(quote[1])}</blockquote>`);
          continue;
        }

        const unordered = /^[-*]\\s+(\\[[ xX]\\]\\s+)?(.+)$/.exec(trimmed);
        if (unordered) {
          flushParagraph(paragraph, html);
          openList("ul");
          const checkbox = unordered[1]
            ? `<input class="task-checkbox" type="checkbox" disabled ${/\\[[xX]\\]/.test(unordered[1]) ? "checked" : ""}>`
            : "";
          html.push(`<li>${checkbox}${renderInlineMarkdown(unordered[2])}</li>`);
          continue;
        }

        const ordered = /^\\d+[.)]\\s+(.+)$/.exec(trimmed);
        if (ordered) {
          flushParagraph(paragraph, html);
          openList("ol");
          html.push(`<li>${renderInlineMarkdown(ordered[1])}</li>`);
          continue;
        }

        closeList();
        paragraph.push(trimmed);
      }

      if (inCode) {
        html.push(`<pre><code>${escapeHtml(codeLines.join("\\n"))}</code></pre>`);
      }
      flushParagraph(paragraph, html);
      closeList();
      return html.join("");
    }

    function setResultText(value) {
      rawResultText = String(value ?? "");
      result.innerHTML = renderMarkdown(rawResultText);
      result.scrollTop = 0;
    }

    function appendResultText(value) {
      rawResultText += String(value ?? "");
      result.innerHTML = renderMarkdown(rawResultText);
      result.scrollTop = result.scrollHeight;
    }

    function collectOpsContext() {
      return {
        model: modelSelect.value,
        multi_agent: multiAgent.checked,
        goal: {
          title: goalTitle.value.trim(),
          criteria: lineList(goalCriteria.value),
          constraints: lineList(goalConstraints.value),
          notes: [],
        },
        plan: {
          title: planTitle.value.trim(),
          steps: lineList(planSteps.value),
        },
        attach_path: attachPath.value.trim(),
        scaffold_text: scaffoldText.value.trim(),
      };
    }

    async function loadModels() {
      const response = await fetch("/api/models");
      const data = await response.json();
      modelSelect.innerHTML = "";
      for (const model of data.models) {
        const option = document.createElement("option");
        option.value = model;
        option.textContent = model;
        if (model === data.default_model) {
          option.selected = true;
        }
        modelSelect.appendChild(option);
      }
    }

    async function loadPrompts() {
      const response = await fetch("/api/prompts");
      const data = await response.json();
      savedPrompts.innerHTML = "";

      const empty = document.createElement("option");
      empty.value = "";
      empty.textContent = "저장된 프롬프트 선택";
      savedPrompts.appendChild(empty);

      for (const item of data.prompts) {
        const option = document.createElement("option");
        option.value = item.name;
        option.textContent = item.name;
        option.dataset.content = item.content;
        option.dataset.category = item.category || "";
        option.dataset.tags = (item.tags || []).join(", ");
        savedPrompts.appendChild(option);
      }
    }

    async function postJson(url, payload) {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "요청 실패");
      }
      return data;
    }

    function parseSseBlock(block) {
      let eventName = "message";
      const dataLines = [];
      for (const rawLine of block.split("\\n")) {
        const line = rawLine.endsWith("\\r") ? rawLine.slice(0, -1) : rawLine;
        if (line.startsWith("event:")) {
          eventName = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
          dataLines.push(line.slice(5).trimStart());
        }
      }
      const dataText = dataLines.join("\\n");
      let data = dataText;
      try {
        data = dataText ? JSON.parse(dataText) : {};
      } catch (_) {
        data = { text: dataText };
      }
      return { eventName, data };
    }

    async function postEventStream(url, payload, onEvent) {
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "text/event-stream",
        },
        body: JSON.stringify(payload),
      });
      if (!response.ok || !response.body) {
        let message = "요청 실패";
        try {
          const data = await response.json();
          message = data.error || message;
        } catch (_) {
          message = await response.text();
        }
        throw new Error(message);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) {
          break;
        }
        buffer += decoder.decode(value, { stream: true });
        const blocks = buffer.split("\\n\\n");
        buffer = blocks.pop() || "";
        for (const block of blocks) {
          if (!block.trim()) {
            continue;
          }
          const parsed = parseSseBlock(block);
          onEvent(parsed.eventName, parsed.data);
        }
      }
      buffer += decoder.decode();
      if (buffer.trim()) {
        const parsed = parseSseBlock(buffer);
        onEvent(parsed.eventName, parsed.data);
      }
    }

    async function runAgentStream(url, payload, actionButton, initialStatus) {
      actionButton.disabled = true;
      statusText.textContent = initialStatus;
      setResultText("");
      let receivedText = false;
      try {
        await postEventStream(url, payload, (eventName, data) => {
          if (eventName === "status") {
            statusText.textContent = data.message || "실행 중...";
          } else if (eventName === "delta") {
            if (!receivedText) {
              setResultText("");
              receivedText = true;
            }
            appendResultText(data.text || "");
          } else if (eventName === "done") {
            statusText.textContent = data.wiki_path ? `완료 / 기록 저장: ${data.wiki_path}` : "완료";
          } else if (eventName === "error") {
            throw new Error(data.error || "실행 실패");
          }
        });
      } catch (error) {
        setResultText(receivedText ? `${rawResultText}\\n\\n오류: ${error.message}` : `오류: ${error.message}`);
        statusText.textContent = "실패";
      } finally {
        actionButton.disabled = false;
      }
    }

    button.addEventListener("click", async () => {
      const prompt = promptInput.value.trim();
      if (!prompt) {
        setResultText("요청 내용을 입력하세요.");
        return;
      }

      await runAgentStream(
        "/api/run-stream",
        {
          prompt,
          model: modelSelect.value,
          multi_agent: multiAgent.checked,
          ...collectOpsContext(),
        },
        button,
        "스트리밍 연결 중..."
      );
    });

    savedPrompts.addEventListener("change", () => {
      const selected = savedPrompts.selectedOptions[0];
      if (!selected || !selected.value) {
        return;
      }
      promptName.value = selected.value;
      promptInput.value = selected.dataset.content || "";
      promptCategory.value = selected.dataset.category || "";
      promptTags.value = selected.dataset.tags || "";
      statusText.textContent = "프롬프트 불러옴";
    });

    savePromptButton.addEventListener("click", async () => {
      const name = promptName.value.trim();
      const content = promptInput.value.trim();
      if (!name || !content) {
        statusText.textContent = "이름/내용 필요";
        return;
      }

      savePromptButton.disabled = true;
      try {
        await postJson("/api/prompts/save", {
          name,
          content,
          category: promptCategory.value.trim(),
          tags: lineList(promptTags.value.replaceAll(",", "\\n")),
        });
        await loadPrompts();
        savedPrompts.value = name;
        statusText.textContent = "프롬프트 저장됨";
      } catch (error) {
        setResultText(`프롬프트 저장 실패: ${error.message}`);
        statusText.textContent = "저장 실패";
      } finally {
        savePromptButton.disabled = false;
      }
    });

    saveGoalButton.addEventListener("click", async () => {
      saveGoalButton.disabled = true;
      try {
        const data = await postJson("/api/goals/save", collectOpsContext());
        statusText.textContent = `목표 저장됨: ${data.path}`;
      } catch (error) {
        setResultText(`목표 저장 실패: ${error.message}`);
        statusText.textContent = "목표 저장 실패";
      } finally {
        saveGoalButton.disabled = false;
      }
    });

    savePlanButton.addEventListener("click", async () => {
      savePlanButton.disabled = true;
      try {
        const data = await postJson("/api/plans/save", collectOpsContext());
        statusText.textContent = `플랜 저장됨: ${data.path}`;
      } catch (error) {
        setResultText(`플랜 저장 실패: ${error.message}`);
        statusText.textContent = "플랜 저장 실패";
      } finally {
        savePlanButton.disabled = false;
      }
    });

    sampleScaffoldButton.addEventListener("click", async () => {
      try {
        const data = await postJson("/api/scaffold/sample", {});
        scaffoldText.value = data.sample;
        statusText.textContent = "생성기 예시 입력됨";
      } catch (error) {
        setResultText(`예시 로드 실패: ${error.message}`);
      }
    });

    previewScaffoldButton.addEventListener("click", async () => {
      previewScaffoldButton.disabled = true;
      try {
        const data = await postJson("/api/scaffold/preview", collectOpsContext());
        setResultText(data.summary);
        statusText.textContent = "생성 미리보기 완료";
      } catch (error) {
        setResultText(`미리보기 실패: ${error.message}`);
        statusText.textContent = "미리보기 실패";
      } finally {
        previewScaffoldButton.disabled = false;
      }
    });

    applyScaffoldButton.addEventListener("click", async () => {
      applyScaffoldButton.disabled = true;
      try {
        const data = await postJson("/api/scaffold/apply", collectOpsContext());
        setResultText(data.summary);
        statusText.textContent = `자동 생성 완료: ${data.summary_path}`;
      } catch (error) {
        setResultText(`자동 생성 실패: ${error.message}`);
        statusText.textContent = "자동 생성 실패";
      } finally {
        applyScaffoldButton.disabled = false;
      }
    });

    runScaffoldButton.addEventListener("click", async () => {
      const prompt = promptInput.value.trim();
      if (!prompt) {
        setResultText("요청 내용을 입력하세요.");
        return;
      }
      await runAgentStream(
        "/api/scaffold/run-stream",
        {
          prompt,
          ...collectOpsContext(),
        },
        runScaffoldButton,
        "파일 생성 후 스트리밍 실행 중..."
      );
    });

    catalogButton.addEventListener("click", async () => {
      try {
        const data = await postJson("/api/catalog", {});
        setResultText(data.markdown);
        statusText.textContent = `모델 카탈로그 저장: ${data.path}`;
      } catch (error) {
        setResultText(`카탈로그 실패: ${error.message}`);
      }
    });

    experimentButton.addEventListener("click", async () => {
      const prompt = promptInput.value.trim();
      if (!prompt) {
        setResultText("비교할 요청 내용을 입력하세요.");
        return;
      }
      experimentButton.disabled = true;
      statusText.textContent = "모델 비교 실험 중...";
      try {
        const data = await postJson("/api/experiment", {
          prompt,
          ...collectOpsContext(),
        });
        setResultText(data.summary);
        statusText.textContent = `실험 저장: ${data.path}`;
      } catch (error) {
        setResultText(`실험 실패: ${error.message}`);
        statusText.textContent = "실험 실패";
      } finally {
        experimentButton.disabled = false;
      }
    });

    registerScanButton.addEventListener("click", async () => {
      const project_path = registerPath.value.trim();
      if (!project_path) {
        setResultText("프로젝트 경로를 입력하세요.");
        return;
      }
      registerScanButton.disabled = true;
      try {
        const data = await postJson("/api/register/scan", { project_path });
        setResultText(data.report);
        statusText.textContent = "등록 분석 완료";
      } catch (error) {
        setResultText(`등록 분석 실패: ${error.message}`);
        statusText.textContent = "등록 분석 실패";
      } finally {
        registerScanButton.disabled = false;
      }
    });

    registerScaffoldButton.addEventListener("click", async () => {
      const project_path = registerPath.value.trim();
      if (!project_path) {
        setResultText("프로젝트 경로를 입력하세요.");
        return;
      }
      registerScaffoldButton.disabled = true;
      try {
        const data = await postJson("/api/register/scaffold", { project_path });
        setResultText(data.report);
        statusText.textContent = `등록 구조 생성: ${data.workspace}`;
      } catch (error) {
        setResultText(`등록 구조 생성 실패: ${error.message}`);
        statusText.textContent = "등록 구조 생성 실패";
      } finally {
        registerScaffoldButton.disabled = false;
      }
    });

    registerPackageButton.addEventListener("click", async () => {
      const project_path = registerPath.value.trim();
      if (!project_path) {
        setResultText("프로젝트 경로를 입력하세요.");
        return;
      }
      registerPackageButton.disabled = true;
      try {
        const data = await postJson("/api/register/package", { project_path });
        setResultText(`${data.report}\n\n## Registration Package\n\n- ${data.package_path}`);
        statusText.textContent = `등록 패키지 생성: ${data.package_path}`;
      } catch (error) {
        setResultText(`등록 패키지 생성 실패: ${error.message}`);
        statusText.textContent = "등록 패키지 생성 실패";
      } finally {
        registerPackageButton.disabled = false;
      }
    });

    registerFixLogButton.addEventListener("click", async () => {
      const log_path = registerLogPath.value.trim();
      if (!log_path) {
        setResultText("오류 로그 파일 경로를 입력하세요.");
        return;
      }
      registerFixLogButton.disabled = true;
      try {
        const data = await postJson("/api/register/fix-log", { log_path, project_path: registerPath.value.trim() });
        setResultText(`${data.report}\n\n${data.patch_report || ""}`);
        statusText.textContent = `오류 분석 저장: ${data.path}`;
      } catch (error) {
        setResultText(`오류 로그 분석 실패: ${error.message}`);
        statusText.textContent = "오류 분석 실패";
      } finally {
        registerFixLogButton.disabled = false;
      }
    });

    deletePromptButton.addEventListener("click", async () => {
      const name = promptName.value.trim() || savedPrompts.value;
      if (!name) {
        statusText.textContent = "삭제할 프롬프트 없음";
        return;
      }

      deletePromptButton.disabled = true;
      try {
        await postJson("/api/prompts/delete", { name });
        await loadPrompts();
        promptName.value = "";
        statusText.textContent = "프롬프트 삭제됨";
      } catch (error) {
        setResultText(`프롬프트 삭제 실패: ${error.message}`);
        statusText.textContent = "삭제 실패";
      } finally {
        deletePromptButton.disabled = false;
      }
    });

    testButton.addEventListener("click", async () => {
      testButton.disabled = true;
      statusText.textContent = "연결 테스트 중...";
      setResultText(`${modelSelect.value} 모델 연결을 확인하는 중입니다.`);

      try {
        const data = await postJson("/api/test-model", {
          model: modelSelect.value,
        });
        setResultText(data.result);
        statusText.textContent = "연결 정상";
      } catch (error) {
        setResultText(`연결 테스트 실패: ${error.message}`);
        statusText.textContent = "연결 실패";
      } finally {
        testButton.disabled = false;
      }
    });

    downloadButton.addEventListener("click", () => {
      const text = rawResultText.trim();
      if (!text || text === "결과가 여기에 표시됩니다.") {
        statusText.textContent = "저장할 결과 없음";
        return;
      }
      const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
      const content = `# DeepAgents 실행 결과\n\n- 모델: ${modelSelect.value}\n- 멀티에이전트: ${multiAgent.checked ? "사용" : "미사용"}\n- 생성일시: ${new Date().toLocaleString()}\n\n## 요청\n\n${promptInput.value.trim()}\n\n## 결과\n\n${text}\n`;
      const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `deepagents-result-${timestamp}.md`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      statusText.textContent = "다운로드 완료";
    });

    loadModels().catch((error) => {
      setResultText(`모델 목록 로드 실패: ${error.message}`);
    });
    loadPrompts().catch((error) => {
      setResultText(`프롬프트 목록 로드 실패: ${error.message}`);
    });
  </script>
</body>
</html>
"""


def format_agent_result(result) -> str:
    if isinstance(result, dict) and "messages" in result:
        messages = result["messages"]
        if messages:
            last_message = messages[-1]
            if isinstance(last_message, dict) and last_message.get("content"):
                return stringify_message_content(last_message["content"])
            content = getattr(last_message, "content", None)
            if content:
                return stringify_message_content(content)
    return str(result)


def stringify_message_content(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content") or item.get("value")
                if text:
                    parts.append(str(text))
            elif item:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def extract_stream_text(chunk, depth: int = 0) -> str:
    if depth > 4:
        return ""
    if isinstance(chunk, str):
        return chunk
    content = getattr(chunk, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(chunk, list):
        for item in reversed(chunk):
            text = extract_stream_text(item, depth + 1)
            if text:
                return text
        return ""
    if isinstance(chunk, dict):
        for key in ("content", "delta", "text"):
            value = chunk.get(key)
            if isinstance(value, str):
                return value
        messages = chunk.get("messages")
        if isinstance(messages, list) and messages:
            last_message = messages[-1]
            if isinstance(last_message, dict) and isinstance(last_message.get("content"), str):
                return last_message["content"]
            message_content = getattr(last_message, "content", None)
            if isinstance(message_content, str):
                return message_content
        for value in chunk.values():
            if isinstance(value, (dict, list)):
                text = extract_stream_text(value, depth + 1)
                if text:
                    return text
    return ""


def iter_text_chunks(value: str, chunk_size: int = STREAM_CHUNK_CHARS):
    text = str(value)
    for index in range(0, len(text), chunk_size):
        yield text[index : index + chunk_size]


def invoke_agent_text(agent, request: dict, on_delta=None, on_status=None, allow_format_retry: bool = True) -> tuple[str, bool]:
    alternate_request = build_alternate_agent_request(request) if allow_format_retry else None
    stream = getattr(agent, "stream", None)
    if not callable(stream):
        if on_status:
            on_status("모델 응답 대기 중...")
        try:
            return format_agent_result(agent.invoke(request)), False
        except Exception as exc:
            if alternate_request is None or not is_message_format_error(exc):
                raise
            if on_status:
                on_status("메시지 포맷 호환 재시도 중...")
            return format_agent_result(agent.invoke(alternate_request)), False

    last_chunk = None
    last_text = ""
    saw_text = False
    streamed = False
    try:
        if on_status:
            on_status("모델 스트림 수신 중...")
        for chunk in stream(request):
            last_chunk = chunk
            text = extract_stream_text(chunk)
            if not text:
                continue
            saw_text = True
            if text.startswith(last_text):
                delta = text[len(last_text) :]
                last_text = text
            else:
                delta = text
                last_text += text
            if delta and on_delta:
                streamed = True
                on_delta(delta)
        if saw_text:
            return last_text, streamed
        if streamed:
            return last_text, True
        if last_chunk is not None:
            return format_agent_result(last_chunk), False
    except Exception as exc:
        if alternate_request is not None and is_message_format_error(exc):
            if on_status:
                on_status("메시지 포맷 호환 재시도 중...")
            return invoke_agent_text(
                agent,
                alternate_request,
                on_delta=on_delta,
                on_status=on_status,
                allow_format_retry=False,
            )
        if on_status:
            on_status(f"스트림 수신 실패, 일반 호출로 전환: {exc}")

    if on_status:
        on_status("일반 호출로 최종 응답 대기 중...")
    try:
        return format_agent_result(agent.invoke(request)), False
    except Exception as exc:
        if alternate_request is None or not is_message_format_error(exc):
            raise
        if on_status:
            on_status("메시지 포맷 호환 재시도 중...")
        return format_agent_result(agent.invoke(alternate_request)), False


def load_prompt_store() -> list[dict[str, str]]:
    if not PROMPT_STORE_PATH.exists():
        return []

    try:
        data = json.loads(PROMPT_STORE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    prompts = data.get("prompts", []) if isinstance(data, dict) else []
    clean_prompts = []
    for item in prompts:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        content = str(item.get("content", "")).strip()
        category = str(item.get("category", "")).strip()
        tags = item.get("tags", [])
        if isinstance(tags, str):
            tags = [part.strip() for part in tags.split(",") if part.strip()]
        elif isinstance(tags, list):
            tags = [str(part).strip() for part in tags if str(part).strip()]
        else:
            tags = []
        if name and content:
            clean_prompts.append({"name": name, "content": content, "category": category, "tags": tags})
    return clean_prompts


def save_prompt_store(prompts: list[dict[str, str]]) -> None:
    PROMPT_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"prompts": sorted(prompts, key=lambda item: item["name"])}
    PROMPT_STORE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def slugify(value: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z가-힣_-]+", "-", value.strip())
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    return normalized[:60] or "run"


def markdown_escape(value: str) -> str:
    return value.replace("|", "\\|").strip()


def mask_sensitive(value: str) -> str:
    if not MASK_SENSITIVE_LOGS:
        return value
    masked = re.sub(r"(?i)(api[_-]?key|authorization|bearer)\s*[:=]\s*[\w./+=-]+", r"\1=***", value)
    masked = re.sub(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", "xxx.xxx.xxx.xxx", masked)
    return masked


def render_web_plan_markdown(plan: dict, *, model_name: str, enable_multi_agent: bool) -> str:
    title = str(plan.get("title") or "Untitled Plan").strip()
    steps = [str(item).strip() for item in plan.get("steps", []) if str(item).strip()]
    lines = [
        f"# {title}",
        "",
        f"- Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Model: {model_name}",
        f"- Multi Agent: {'enabled' if enable_multi_agent else 'disabled'}",
        "",
        "## Steps",
        "",
    ]
    lines.extend([f"- [ ] {step}" for step in steps] or ["- [ ] No steps yet"])
    lines.append("")
    return "\n".join(lines)


def save_web_plan(plan: dict, *, model_name: str, enable_multi_agent: bool) -> Path:
    title = str(plan.get("title") or "").strip()
    steps = [str(item).strip() for item in plan.get("steps", []) if str(item).strip()]
    if not title and not steps:
        raise ValueError("플랜 제목 또는 단계가 필요합니다.")
    PLAN_DIR.mkdir(parents=True, exist_ok=True)
    path = PLAN_DIR / f"{common_slugify(title or 'web-plan', 'plan')}.md"
    path.write_text(render_web_plan_markdown({"title": title, "steps": steps}, model_name=model_name, enable_multi_agent=enable_multi_agent), encoding="utf-8")
    return path


def build_context_files(payload: dict, *, model_name: str, enable_multi_agent: bool) -> dict[str, str]:
    files = get_harness_skill_files()
    goal = payload.get("goal") if isinstance(payload.get("goal"), dict) else {}
    plan = payload.get("plan") if isinstance(payload.get("plan"), dict) else {}
    if goal and (goal.get("title") or goal.get("criteria") or goal.get("constraints") or goal.get("notes")):
        files["/goals/current-goal.md"] = goal_to_markdown(goal, model_name=model_name, multi_agent=enable_multi_agent)
    if plan and (plan.get("title") or plan.get("steps")):
        files["/plans/current-plan.md"] = render_web_plan_markdown(plan, model_name=model_name, enable_multi_agent=enable_multi_agent)

    attach_path = str(payload.get("attach_path", "")).strip()
    if attach_path:
        path = Path(attach_path)
        if not path.is_absolute():
            path = WORKSPACE_DIR / path
        path = path.resolve()
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"첨부 파일을 찾을 수 없습니다: {path}")
        try:
            relative = path.relative_to(WORKSPACE_DIR.resolve()).as_posix()
            virtual_path = f"/workspace/{relative}"
        except ValueError:
            virtual_path = f"/workspace_external/{path.name}"
        files[virtual_path] = path.read_text(encoding="utf-8")
    return files


def scaffold_payload(payload: dict, *, model_name: str, enable_multi_agent: bool, write_files: bool):
    text = str(payload.get("scaffold_text", "")).strip()
    if not text:
        raise ValueError("작업 생성기 텍스트가 비어 있습니다.")
    spec = parse_scaffold_text(text)
    result = apply_scaffold(
        spec,
        WORKSPACE_DIR,
        plan_dir=PLAN_DIR,
        session_dir=session_dir(),
        model_name=model_name,
        enable_multi_agent=enable_multi_agent,
        write_files=write_files,
    )
    return spec, result


def scaffold_result_payload(spec, result) -> dict:
    return {
        "summary": render_scaffold_summary(spec, result),
        "summary_path": result.summary_path.as_posix() if result.summary_path else "",
        "created_dirs": [path.as_posix() for path in result.created_dirs],
        "created_files": [path.as_posix() for path in result.created_files],
        "goal_path": result.goal_path.as_posix() if result.goal_path else "",
        "plan_path": result.plan_path.as_posix() if result.plan_path else "",
    }


def save_wiki_record(
    *,
    prompt: str,
    result: str,
    model_name: str,
    enable_multi_agent: bool,
    goal_title: str = "",
) -> str:
    now = datetime.now()
    day = now.strftime("%Y-%m-%d")
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    clean_prompt = mask_sensitive(prompt)
    clean_result = mask_sensitive(result)
    filename = f"{now.strftime('%H%M%S')}-{slugify(clean_prompt)}.md"
    day_dir = WIKI_LOG_DIR / day
    day_dir.mkdir(parents=True, exist_ok=True)
    record_path = day_dir / filename
    base_url = os.getenv("QWEN_BASE_URL", "")
    model_list = ", ".join(MODEL_OPTIONS)

    record_path.write_text(
        "\n".join(
            [
                f"# vLLM 실행 기록 - {clean_prompt[:80]}",
                "",
                "## vLLM Serving",
                "",
                f"- Created: {timestamp}",
                f"- Model: {model_name}",
                f"- Registered Models: {model_list}",
                f"- OpenAI Compatible Base URL: {base_url or 'not configured'}",
                f"- Goal: {goal_title or 'not set'}",
                "- Chat Completions Path: /chat/completions",
                "- Tool Calling Required: yes",
                "- API Key Stored: no",
                "",
                "## DeepAgents Runtime",
                "",
                f"- Multi Agent: {'enabled' if enable_multi_agent else 'disabled'}",
                f"- Harness Skills: {'enabled' if harness_skills_enabled() else 'disabled'}",
                f"- Skill List: {', '.join(get_harness_skill_names()) or 'none'}",
                "- External Web Tools: disabled",
                "- Internal Tools: make_security_todo",
                "- Subagents: security-checker, report-writer",
                "",
                "## Prompt",
                "",
                clean_prompt,
                "",
                "## Result",
                "",
                clean_result,
                "",
            ]
        ),
        encoding="utf-8",
    )
    rebuild_wiki_index()
    return record_path.as_posix()


def rebuild_wiki_index() -> None:
    WIKI_LOG_DIR.mkdir(parents=True, exist_ok=True)
    record_meta = []
    for record in sorted(WIKI_LOG_DIR.glob("*/*.md"), reverse=True):
        try:
            content = record.read_text(encoding="utf-8")
        except OSError:
            continue
        model = "unknown"
        goal = "not set"
        for line in content.splitlines():
            if line.startswith("- Model:"):
                model = line.split(":", 1)[1].strip() or "unknown"
            elif line.startswith("- Goal:"):
                goal = line.split(":", 1)[1].strip() or "not set"
        record_meta.append({"path": record, "model": model, "goal": goal})

    lines = [
        "# vLLM DeepAgents 실행 기록 Wiki",
        "",
        "## Environment",
        "",
        f"- Wiki Style: {WIKI_LOG_STYLE}",
        f"- Registered Models: {', '.join(MODEL_OPTIONS)}",
        f"- Default Model: {DEFAULT_MODEL}",
        f"- OpenAI Compatible Base URL: {os.getenv('QWEN_BASE_URL', 'not configured')}",
        f"- Harness Skills: {'enabled' if harness_skills_enabled() else 'disabled'}",
        f"- Skill List: {', '.join(get_harness_skill_names()) or 'none'}",
        "- API Key: not recorded",
        "- Tool Calling: required",
        "",
        "## Tree",
        "",
        "```text",
        "wiki_logs/",
    ]

    day_dirs = sorted([path for path in WIKI_LOG_DIR.iterdir() if path.is_dir()], reverse=True)
    for day_dir in day_dirs:
        lines.append(f"├─ {day_dir.name}/")
        records = sorted(day_dir.glob("*.md"), reverse=True)
        for index, record in enumerate(records):
            prefix = "└─" if index == len(records) - 1 else "├─"
            lines.append(f"│  {prefix} {record.name}")
    lines.extend(["```", "", "## Records", ""])

    for day_dir in day_dirs:
        lines.extend([f"### {day_dir.name}", ""])
        for record in sorted(day_dir.glob("*.md"), reverse=True):
            relative = record.relative_to(WIKI_LOG_DIR).as_posix()
            title = record.stem.split("-", 1)[-1].replace("-", " ")
            lines.append(f"- [{markdown_escape(title)}]({relative})")
        lines.append("")

    lines.extend(["## By Model", ""])
    for model in sorted({item["model"] for item in record_meta}):
        lines.extend([f"### {model}", ""])
        for item in [entry for entry in record_meta if entry["model"] == model]:
            relative = item["path"].relative_to(WIKI_LOG_DIR).as_posix()
            title = item["path"].stem.split("-", 1)[-1].replace("-", " ")
            lines.append(f"- [{markdown_escape(title)}]({relative})")
        lines.append("")

    lines.extend(["## By Goal", ""])
    for goal in sorted({item["goal"] for item in record_meta}):
        lines.extend([f"### {goal}", ""])
        for item in [entry for entry in record_meta if entry["goal"] == goal]:
            relative = item["path"].relative_to(WIKI_LOG_DIR).as_posix()
            title = item["path"].stem.split("-", 1)[-1].replace("-", " ")
            lines.append(f"- [{markdown_escape(title)}]({relative})")
        lines.append("")

    (WIKI_LOG_DIR / "index.md").write_text("\n".join(lines), encoding="utf-8")


class AgentHandler(BaseHTTPRequestHandler):
    agents = {}

    def do_GET(self) -> None:
        if self.path == "/api/models":
            self._send_json(
                {
                    "models": MODEL_OPTIONS,
                    "default_model": DEFAULT_MODEL,
                }
            )
            return
        if self.path == "/api/prompts":
            self._send_json({"prompts": load_prompt_store()})
            return
        if self.path == "/api/workspace":
            WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
            files = [path.relative_to(WORKSPACE_DIR).as_posix() for path in sorted(WORKSPACE_DIR.rglob("*")) if path.is_file()]
            self._send_json({"workspace": str(WORKSPACE_DIR.resolve()), "files": files[:200]})
            return
        if self.path not in ("/", "/index.html"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self._send_html(HTML)

    def do_POST(self) -> None:
        if self.path not in (
            "/api/run",
            "/api/run-stream",
            "/api/test-model",
            "/api/catalog",
            "/api/experiment",
            "/api/scaffold/sample",
            "/api/scaffold/preview",
            "/api/scaffold/apply",
            "/api/scaffold/run",
            "/api/scaffold/run-stream",
            "/api/register/scan",
            "/api/register/scaffold",
            "/api/register/package",
            "/api/register/fix-log",
            "/api/prompts/save",
            "/api/prompts/delete",
            "/api/goals/save",
            "/api/plans/save",
        ):
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))

            if self.path == "/api/prompts/save":
                self._save_prompt(payload)
                return
            if self.path == "/api/prompts/delete":
                self._delete_prompt(payload)
                return
            if self.path == "/api/goals/save":
                self._save_goal(payload)
                return
            if self.path == "/api/plans/save":
                self._save_plan(payload)
                return
            if self.path == "/api/catalog":
                self._catalog()
                return
            if self.path == "/api/experiment":
                self._experiment(payload)
                return
            if self.path == "/api/scaffold/sample":
                self._send_json({"sample": SCAFFOLD_SAMPLE})
                return
            if self.path == "/api/scaffold/preview":
                self._scaffold(payload, write_files=False)
                return
            if self.path == "/api/scaffold/apply":
                self._scaffold(payload, write_files=True)
                return
            if self.path == "/api/run-stream":
                self._run_stream(payload)
                return
            if self.path == "/api/scaffold/run":
                self._scaffold_run(payload)
                return
            if self.path == "/api/scaffold/run-stream":
                self._scaffold_run_stream(payload)
                return
            if self.path == "/api/register/scan":
                self._register_scan(payload)
                return
            if self.path == "/api/register/scaffold":
                self._register_scaffold(payload)
                return
            if self.path == "/api/register/package":
                self._register_package(payload)
                return
            if self.path == "/api/register/fix-log":
                self._register_fix_log(payload)
                return

            prompt = str(payload.get("prompt", "")).strip()
            model_name = str(payload.get("model") or DEFAULT_MODEL).strip()
            enable_multi_agent = bool(payload.get("multi_agent", True))
            if model_name not in MODEL_OPTIONS:
                self._send_json({"error": f"등록되지 않은 모델입니다: {model_name}"}, HTTPStatus.BAD_REQUEST)
                return

            if self.path == "/api/test-model":
                prompt = "연결 테스트입니다. 'OK'와 현재 사용 모델명을 짧게 답하세요."
                enable_multi_agent = False
            elif not prompt:
                self._send_json({"error": "prompt 값이 비어 있습니다."}, HTTPStatus.BAD_REQUEST)
                return

            agent = self._get_agent(model_name, enable_multi_agent)
            files = build_context_files(payload, model_name=model_name, enable_multi_agent=enable_multi_agent)
            response = invoke_agent_compatible(agent, prompt, files)
            result_text = format_agent_result(response)
            wiki_path = None
            if self.path == "/api/run":
                wiki_path = save_wiki_record(
                    prompt=prompt,
                    result=result_text,
                    model_name=model_name,
                    enable_multi_agent=enable_multi_agent,
                    goal_title=str((payload.get("goal") or {}).get("title", "")),
                )
            self._send_json({"result": result_text, "wiki_path": wiki_path})
        except Exception as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def _run_stream(self, payload: dict) -> None:
        self._send_sse_headers()
        try:
            prompt = str(payload.get("prompt", "")).strip()
            model_name = str(payload.get("model") or DEFAULT_MODEL).strip()
            enable_multi_agent = bool(payload.get("multi_agent", True))
            if not prompt:
                self._send_sse("error", {"error": "prompt 값이 비어 있습니다."})
                return
            if model_name not in MODEL_OPTIONS:
                self._send_sse("error", {"error": f"등록되지 않은 모델입니다: {model_name}"})
                return

            self._send_sse("status", {"message": "컨텍스트 파일 구성 중..."})
            files = build_context_files(payload, model_name=model_name, enable_multi_agent=enable_multi_agent)
            self._stream_agent_result(
                prompt=prompt,
                model_name=model_name,
                enable_multi_agent=enable_multi_agent,
                files=files,
                goal_title=str((payload.get("goal") or {}).get("title", "")),
            )
        except Exception as exc:
            self._send_sse("error", {"error": str(exc)})
        finally:
            self.close_connection = True

    def _save_prompt(self, payload: dict) -> None:
        name = str(payload.get("name", "")).strip()
        content = str(payload.get("content", "")).strip()
        category = str(payload.get("category", "")).strip()
        tags = payload.get("tags", [])
        if isinstance(tags, str):
            tags = [part.strip() for part in tags.split(",") if part.strip()]
        elif isinstance(tags, list):
            tags = [str(part).strip() for part in tags if str(part).strip()]
        else:
            tags = []
        if not name or not content:
            self._send_json({"error": "name과 content가 필요합니다."}, HTTPStatus.BAD_REQUEST)
            return
        if len(name) > 80:
            self._send_json({"error": "프롬프트 이름은 80자 이하로 입력하세요."}, HTTPStatus.BAD_REQUEST)
            return

        prompts = [item for item in load_prompt_store() if item["name"] != name]
        prompts.append({"name": name, "content": content, "category": category, "tags": tags})
        save_prompt_store(prompts)
        self._send_json({"ok": True, "prompts": load_prompt_store()})

    def _delete_prompt(self, payload: dict) -> None:
        name = str(payload.get("name", "")).strip()
        if not name:
            self._send_json({"error": "name이 필요합니다."}, HTTPStatus.BAD_REQUEST)
            return

        prompts = [item for item in load_prompt_store() if item["name"] != name]
        save_prompt_store(prompts)
        self._send_json({"ok": True, "prompts": prompts})

    def _save_goal(self, payload: dict) -> None:
        goal = payload.get("goal") if isinstance(payload.get("goal"), dict) else {}
        model_name = str(payload.get("model") or DEFAULT_MODEL).strip()
        enable_multi_agent = bool(payload.get("multi_agent", True))
        try:
            path = save_goal_markdown(goal, model_name=model_name, multi_agent=enable_multi_agent)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        self._send_json({"ok": True, "path": path.as_posix()})

    def _catalog(self) -> None:
        catalog, json_path = ensure_model_catalog(MODEL_OPTIONS)
        md_path = save_model_catalog_markdown(catalog)
        self._send_json(
            {
                "ok": True,
                "path": json_path.as_posix(),
                "markdown_path": md_path.as_posix(),
                "markdown": md_path.read_text(encoding="utf-8"),
            }
        )

    def _scaffold(self, payload: dict, *, write_files: bool) -> None:
        model_name = str(payload.get("model") or DEFAULT_MODEL).strip()
        enable_multi_agent = bool(payload.get("multi_agent", True))
        spec, result = scaffold_payload(
            payload,
            model_name=model_name,
            enable_multi_agent=enable_multi_agent,
            write_files=write_files,
        )
        self._send_json(scaffold_result_payload(spec, result))

    def _scaffold_run(self, payload: dict) -> None:
        prompt = str(payload.get("prompt", "")).strip()
        model_name = str(payload.get("model") or DEFAULT_MODEL).strip()
        enable_multi_agent = bool(payload.get("multi_agent", True))
        if not prompt:
            self._send_json({"error": "prompt 값이 비어 있습니다."}, HTTPStatus.BAD_REQUEST)
            return
        if model_name not in MODEL_OPTIONS:
            self._send_json({"error": f"등록되지 않은 모델입니다: {model_name}"}, HTTPStatus.BAD_REQUEST)
            return
        spec, scaffold_result = scaffold_payload(
            payload,
            model_name=model_name,
            enable_multi_agent=enable_multi_agent,
            write_files=True,
        )
        files = build_context_files(payload, model_name=model_name, enable_multi_agent=enable_multi_agent)
        files.update(scaffold_to_context_files(WORKSPACE_DIR, scaffold_result))
        if spec.goal.get("title"):
            files["/goals/current-goal.md"] = goal_to_markdown(
                spec.goal,
                model_name=model_name,
                multi_agent=enable_multi_agent,
            )
        if spec.plan_steps:
            files["/plans/current-plan.md"] = render_web_plan_markdown(
                {"title": spec.plan_title, "steps": spec.plan_steps},
                model_name=model_name,
                enable_multi_agent=enable_multi_agent,
            )
        agent = self._get_agent(model_name, enable_multi_agent)
        response = invoke_agent_compatible(agent, prompt, files)
        result_text = format_agent_result(response)
        wiki_path = save_wiki_record(
            prompt=prompt,
            result=result_text,
            model_name=model_name,
            enable_multi_agent=enable_multi_agent,
            goal_title=str(spec.goal.get("title") or (payload.get("goal") or {}).get("title", "")),
        )
        payload_data = scaffold_result_payload(spec, scaffold_result)
        payload_data.update({"result": result_text, "wiki_path": wiki_path})
        self._send_json(payload_data)

    def _scaffold_run_stream(self, payload: dict) -> None:
        self._send_sse_headers()
        try:
            prompt = str(payload.get("prompt", "")).strip()
            model_name = str(payload.get("model") or DEFAULT_MODEL).strip()
            enable_multi_agent = bool(payload.get("multi_agent", True))
            if not prompt:
                self._send_sse("error", {"error": "prompt 값이 비어 있습니다."})
                return
            if model_name not in MODEL_OPTIONS:
                self._send_sse("error", {"error": f"등록되지 않은 모델입니다: {model_name}"})
                return

            self._send_sse("status", {"message": "폴더와 파일 자동 생성 중..."})
            spec, scaffold_result = scaffold_payload(
                payload,
                model_name=model_name,
                enable_multi_agent=enable_multi_agent,
                write_files=True,
            )
            files = build_context_files(payload, model_name=model_name, enable_multi_agent=enable_multi_agent)
            files.update(scaffold_to_context_files(WORKSPACE_DIR, scaffold_result))
            if spec.goal.get("title"):
                files["/goals/current-goal.md"] = goal_to_markdown(
                    spec.goal,
                    model_name=model_name,
                    multi_agent=enable_multi_agent,
                )
            if spec.plan_steps:
                files["/plans/current-plan.md"] = render_web_plan_markdown(
                    {"title": spec.plan_title, "steps": spec.plan_steps},
                    model_name=model_name,
                    enable_multi_agent=enable_multi_agent,
                )
            self._send_sse(
                "status",
                {"message": f"자동 생성 완료: {len(scaffold_result.created_files)}개 파일 컨텍스트 첨부"},
            )
            self._stream_agent_result(
                prompt=prompt,
                model_name=model_name,
                enable_multi_agent=enable_multi_agent,
                files=files,
                goal_title=str(spec.goal.get("title") or (payload.get("goal") or {}).get("title", "")),
            )
        except Exception as exc:
            self._send_sse("error", {"error": str(exc)})
        finally:
            self.close_connection = True

    def _stream_agent_result(
        self,
        *,
        prompt: str,
        model_name: str,
        enable_multi_agent: bool,
        files: dict[str, str],
        goal_title: str = "",
    ) -> None:
        self._send_sse("status", {"message": f"{model_name} 에이전트 준비 중..."})
        agent = self._get_agent(model_name, enable_multi_agent)
        request = build_agent_request(prompt, files)

        def send_delta(delta: str) -> None:
            for chunk in iter_text_chunks(delta):
                self._send_sse("delta", {"text": chunk})

        def send_status(message: str) -> None:
            self._send_sse("status", {"message": message})

        result_text, streamed = invoke_agent_text(
            agent,
            request,
            on_delta=send_delta,
            on_status=send_status,
        )
        if not streamed:
            self._send_sse("status", {"message": "최종 응답 표시 중..."})
            send_delta(result_text)

        wiki_path = save_wiki_record(
            prompt=prompt,
            result=result_text,
            model_name=model_name,
            enable_multi_agent=enable_multi_agent,
            goal_title=goal_title,
        )
        self._send_sse("done", {"wiki_path": wiki_path})

    def _experiment(self, payload: dict) -> None:
        prompt = str(payload.get("prompt", "")).strip()
        if not prompt:
            self._send_json({"error": "prompt 값이 비어 있습니다."}, HTTPStatus.BAD_REQUEST)
            return
        selected = str(payload.get("models", "")).strip()
        models = [item.strip() for item in selected.split(",") if item.strip()] if selected else MODEL_OPTIONS
        unknown = [model for model in models if model not in MODEL_OPTIONS]
        if unknown:
            self._send_json({"error": f"등록되지 않은 모델입니다: {', '.join(unknown)}"}, HTTPStatus.BAD_REQUEST)
            return
        enable_multi_agent = bool(payload.get("multi_agent", True))
        files = build_context_files(payload, model_name=models[0], enable_multi_agent=enable_multi_agent)
        results = []
        for model_name in models:
            try:
                agent = self._get_agent(model_name, enable_multi_agent)
                response = invoke_agent_compatible(agent, prompt, files)
                results.append({"model": model_name, "ok": True, "result": format_agent_result(response)})
            except Exception as exc:
                results.append({"model": model_name, "ok": False, "error": str(exc), "result": ""})
        path = save_experiment(
            "web-model-compare",
            prompt,
            results,
            goal_title=str((payload.get("goal") or {}).get("title", "")),
        )
        summary = "\n".join(
            [f"# 모델 비교 실험 저장: {path}", ""]
            + [f"- {item['model']}: {'OK' if item.get('ok') else 'FAIL'}" for item in results]
        )
        self._send_json({"ok": True, "path": path.as_posix(), "summary": summary})

    def _register_scan(self, payload: dict) -> None:
        project_path = str(payload.get("project_path", "")).strip()
        if not project_path:
            self._send_json({"error": "project_path가 필요합니다."}, HTTPStatus.BAD_REQUEST)
            return
        profile = scan_project(project_path)
        json_path, report_path = save_registration_profile(profile)
        self._send_json(
            {
                "ok": True,
                "profile_path": json_path.as_posix(),
                "report_path": report_path.as_posix(),
                "report": render_registration_report(profile),
            }
        )

    def _register_scaffold(self, payload: dict) -> None:
        project_path = str(payload.get("project_path", "")).strip()
        if not project_path:
            self._send_json({"error": "project_path가 필요합니다."}, HTTPStatus.BAD_REQUEST)
            return
        result = scaffold_registered_workspace(project_path)
        report = render_registration_report(result["profile"])
        self._send_json(
            {
                "ok": True,
                "workspace": result["workspace"],
                "files": result["files"],
                "report": report,
            }
        )

    def _register_package(self, payload: dict) -> None:
        project_path = str(payload.get("project_path", "")).strip()
        if not project_path:
            self._send_json({"error": "project_path가 필요합니다."}, HTTPStatus.BAD_REQUEST)
            return
        result = create_registration_package(project_path)
        self._send_json(
            {
                "ok": True,
                "workspace": result["workspace"],
                "package_path": result["package_path"],
                "files": result["files"],
                "readiness": result["readiness"],
                "report": render_registration_report(result["profile"]),
            }
        )

    def _register_fix_log(self, payload: dict) -> None:
        log_path = str(payload.get("log_path", "")).strip()
        if not log_path:
            self._send_json({"error": "log_path가 필요합니다."}, HTTPStatus.BAD_REQUEST)
            return
        report = analyze_log_file(log_path)
        project_path = str(payload.get("project_path", "")).strip()
        workspace = Path(project_path).expanduser() if project_path else Path.cwd()
        if not workspace.is_absolute():
            workspace = (Path.cwd() / workspace).resolve()
        if not workspace.exists() or not workspace.is_dir():
            workspace = Path.cwd()
        report["context"] = {"workspace": workspace.as_posix(), "log_path": log_path}
        path = save_fix_report(report)
        candidates = generate_patch_candidates(report, workspace)
        patch_path = save_patch_candidates(candidates, report["source"])
        self._send_json(
            {
                "ok": True,
                "path": path.as_posix(),
                "patch_path": patch_path.as_posix(),
                "retest_command": report.get("retest_command", ""),
                "report": render_fix_report(report),
                "patch_report": render_patch_candidates(candidates),
            }
        )

    def _save_plan(self, payload: dict) -> None:
        plan = payload.get("plan") if isinstance(payload.get("plan"), dict) else {}
        model_name = str(payload.get("model") or DEFAULT_MODEL).strip()
        enable_multi_agent = bool(payload.get("multi_agent", True))
        try:
            path = save_web_plan(plan, model_name=model_name, enable_multi_agent=enable_multi_agent)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        self._send_json({"ok": True, "path": path.as_posix()})

    def log_message(self, format: str, *args) -> None:
        print(f"[web] {self.address_string()} - {format % args}")

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_sse_headers(self) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

    def _send_sse(self, event_name: str, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False)
        body = f"event: {event_name}\ndata: {data}\n\n".encode("utf-8")
        self.wfile.write(body)
        self.wfile.flush()

    @classmethod
    def _get_agent(cls, model_name: str, enable_multi_agent: bool):
        cache_key = (model_name, enable_multi_agent)
        if cache_key not in cls.agents:
            cls.agents[cache_key] = build_agent(
                model_name=model_name,
                enable_multi_agent=enable_multi_agent,
            )
        return cls.agents[cache_key]


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), AgentHandler)
    print(f"[폐쇄망 웹 모드] http://{HOST}:{PORT} 에서 실행 중입니다.")
    print(f"등록 모델: {', '.join(MODEL_OPTIONS)}")
    print("종료하려면 Ctrl+C를 누르세요.")
    server.serve_forever()


if __name__ == "__main__":
    main()
