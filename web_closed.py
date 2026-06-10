import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app_closed import build_agent
from dotenv import load_dotenv


load_dotenv()

HOST = os.getenv("WEB_HOST", "127.0.0.1")
PORT = int(os.getenv("WEB_PORT", "8000"))

HTML = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>폐쇄망 DeepAgents Kwan PoC</title>
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
    .actions {
      display: flex;
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
  </style>
</head>
<body>
  <main>
    <header>
      <h1>폐쇄망 DeepAgents Kwan PoC</h1>
      <div class="subtitle">외부 검색 없이 내부 Kwan API와 등록된 사내 Tool만 사용합니다.</div>
    </header>
    <section>
      <label for="prompt">요청 내용</label>
      <textarea id="prompt">서버 접근권한 보안 점검 TODO 만들어줘.</textarea>
      <div class="actions">
        <button id="run" type="button">실행</button>
        <span id="status" class="status">대기 중</span>
      </div>
      <pre id="result">결과가 여기에 표시됩니다.</pre>
    </section>
  </main>
  <script>
    const button = document.getElementById("run");
    const statusText = document.getElementById("status");
    const promptInput = document.getElementById("prompt");
    const result = document.getElementById("result");

    button.addEventListener("click", async () => {
      const prompt = promptInput.value.trim();
      if (!prompt) {
        result.textContent = "요청 내용을 입력하세요.";
        return;
      }

      button.disabled = true;
      statusText.textContent = "실행 중...";
      result.textContent = "Kwan API 응답을 기다리는 중입니다.";

      try {
        const response = await fetch("/api/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ prompt }),
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || "요청 실패");
        }
        result.textContent = data.result;
        statusText.textContent = "완료";
      } catch (error) {
        result.textContent = `오류: ${error.message}`;
        statusText.textContent = "실패";
      } finally {
        button.disabled = false;
      }
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
    agent = None

    def do_GET(self) -> None:
        if self.path not in ("/", "/index.html"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self._send_html(HTML)

    def do_POST(self) -> None:
        if self.path != "/api/run":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            prompt = str(payload.get("prompt", "")).strip()
            if not prompt:
                self._send_json({"error": "prompt 값이 비어 있습니다."}, HTTPStatus.BAD_REQUEST)
                return

            response = self.agent.invoke(
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


def main() -> None:
    AgentHandler.agent = build_agent()
    server = ThreadingHTTPServer((HOST, PORT), AgentHandler)
    print(f"[폐쇄망 웹 모드] http://{HOST}:{PORT} 에서 실행 중입니다.")
    print("종료하려면 Ctrl+C를 누르세요.")
    server.serve_forever()


if __name__ == "__main__":
    main()
