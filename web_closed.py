import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app_closed import build_agent, get_available_models, get_default_model
from dotenv import load_dotenv


load_dotenv()

HOST = os.getenv("WEB_HOST", "127.0.0.1")
PORT = int(os.getenv("WEB_PORT", "8000"))
DEFAULT_MODEL = get_default_model()
MODEL_OPTIONS = get_available_models()

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
      width: min(960px, calc(100vw - 32px));
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
    pre {
      min-height: 180px;
      margin: 18px 0 0;
      padding: 16px;
      overflow: auto;
      white-space: pre-wrap;
      word-break: break-word;
      border: 1px solid #dce3ef;
      border-radius: 6px;
      background: #f8fafc;
      line-height: 1.6;
      font-family: "Cascadia Mono", Consolas, monospace;
      font-size: 14px;
    }
    @media (max-width: 680px) {
      .controls {
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
      <label for="prompt">요청 내용</label>
      <textarea id="prompt">서버 접근권한 보안 점검 TODO 만들어줘.</textarea>
      <div class="actions">
        <button id="run" type="button">실행</button>
        <button id="test" class="secondary" type="button">모델 연결 테스트</button>
        <button id="download" class="ghost" type="button">결과 다운로드</button>
        <span id="status" class="status">대기 중</span>
      </div>
      <pre id="result">결과가 여기에 표시됩니다.</pre>
    </section>
  </main>
  <script>
    const button = document.getElementById("run");
    const testButton = document.getElementById("test");
    const downloadButton = document.getElementById("download");
    const statusText = document.getElementById("status");
    const promptInput = document.getElementById("prompt");
    const modelSelect = document.getElementById("model");
    const multiAgent = document.getElementById("multiAgent");
    const result = document.getElementById("result");

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

    button.addEventListener("click", async () => {
      const prompt = promptInput.value.trim();
      if (!prompt) {
        result.textContent = "요청 내용을 입력하세요.";
        return;
      }

      button.disabled = true;
      statusText.textContent = "실행 중...";
      result.textContent = "Qwen 3.5 API 응답을 기다리는 중입니다.";

      try {
        const data = await postJson("/api/run", {
          prompt,
          model: modelSelect.value,
          multi_agent: multiAgent.checked,
        });
        result.textContent = data.result;
        statusText.textContent = "완료";
      } catch (error) {
        result.textContent = `오류: ${error.message}`;
        statusText.textContent = "실패";
      } finally {
        button.disabled = false;
      }
    });

    testButton.addEventListener("click", async () => {
      testButton.disabled = true;
      statusText.textContent = "연결 테스트 중...";
      result.textContent = `${modelSelect.value} 모델 연결을 확인하는 중입니다.`;

      try {
        const data = await postJson("/api/test-model", {
          model: modelSelect.value,
        });
        result.textContent = data.result;
        statusText.textContent = "연결 정상";
      } catch (error) {
        result.textContent = `연결 테스트 실패: ${error.message}`;
        statusText.textContent = "연결 실패";
      } finally {
        testButton.disabled = false;
      }
    });

    downloadButton.addEventListener("click", () => {
      const text = result.textContent.trim();
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
      result.textContent = `모델 목록 로드 실패: ${error.message}`;
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
                return str(last_message["content"])
            content = getattr(last_message, "content", None)
            if content:
                return str(content)
    return str(result)


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
        if self.path not in ("/", "/index.html"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self._send_html(HTML)

    def do_POST(self) -> None:
        if self.path not in ("/api/run", "/api/test-model"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
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
            response = agent.invoke(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ]
                }
            )
            self._send_json({"result": format_agent_result(response)})
        except Exception as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

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
