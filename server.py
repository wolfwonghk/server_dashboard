#!/usr/bin/env python3
"""SERVER 在線檢查 Dashboard — 零依賴 Python 後端（DEVELOPMENT.md §4/§5）.

stdlib http.server（ThreadingHTTPServer + 自訂 handler）：
  - GET /api/status → 讀 servers.csv、ThreadPoolExecutor 平行跑全部探測、回 JSON 陣列
  - 其餘路徑 → 靜檔服務（index.html 等）
探測 2 秒 timeout；timeout/例外一律 DOWN；結果統一
{"name","type","target","up","rtt_ms","checked_at"}。

啟動：
    python3 server.py            # 預設 port 8000
    python3 server.py 9000       # 自訂 port
瀏覽器開啟 http://localhost:8000/
"""
import json
import os
import platform
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

API_STATUS = "/api/status"
CSV_PATH = "servers.csv"
TIMEOUT_S = 2  # 每個探測 2 秒上限（§4）
VALID_TYPES = ("http", "https", "tcp", "ping")
MAX_WORKERS = 32
RTT_RE = re.compile(r"time[=<](\d+(?:\.\d+)?)\s*ms")  # ping 輸出 RTT


# ---------- §3 CSV 解析 ----------
def load_servers(path=CSV_PATH):
    """回傳 (servers, problems)。servers 為 dict 列；problems 為跳過列說明。"""
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    if not lines:
        return [], []
    header = [h.strip().lower() for h in lines[0].split(",")]
    idx = {col: header.index(col) for col in ("name", "type", "host", "port") if col in header}
    for col in ("name", "type", "host"):
        if col not in idx:
            raise ValueError(f"servers.csv 缺少必要欄位「{col}」（表頭：{','.join(header)}）")
    servers, problems = [], []
    for line_no, line in enumerate(lines[1:], start=2):
        cells = [c.strip() for c in line.split(",")]
        get = lambda col: cells[idx[col]] if col in idx and idx[col] < len(cells) else ""  # noqa: E731
        s = {"name": get("name"), "type": get("type").lower(), "host": get("host"), "port": get("port")}
        if not s["name"] or not s["host"] or s["type"] not in VALID_TYPES:
            problems.append(f"第 {line_no} 列跳過（name/type/host 無效）：{line}")
            continue
        if s["type"] != "ping" and s["port"] == "":
            problems.append(f"第 {line_no} 列跳過（{s['type']} 型別需要 port）：{line}")
            continue
        servers.append(s)
    return servers, problems


def target_of(server):
    if server["type"] == "ping":
        return server["host"]
    if server["type"] == "tcp":
        return f"{server['host']}:{server['port']}"
    return f"{server['type']}://{server['host']}:{server['port']}"


# ---------- §4 探測 ----------
def ping_command(host):
    """依平台組系統 ping 指令（§4.3）。"""
    system = platform.system()
    if system == "Windows":
        return ["ping", "-n", "1", "-w", "2000", host]
    if system == "Darwin":
        # macOS BSD ping：-t 為總秒數上限（-W 在此是毫秒且語意不同）
        return ["ping", "-c", "1", "-t", "2", host]
    return ["ping", "-c", "1", "-W", "2", host]  # Linux/POSIX


def probe(server):
    """單一探測：一律回傳 {"name","type","target","up","rtt_ms","checked_at"}。"""
    t0 = time.perf_counter()
    checked_at = datetime.now(timezone.utc).isoformat()
    result = {
        "name": server["name"],
        "type": server["type"],
        "target": target_of(server),
        "up": False,
        "rtt_ms": None,
        "checked_at": checked_at,
    }
    try:
        stype = server["type"]
        if stype in ("http", "https"):
            # §4.1 2xx/3xx → UP（urlopen 自動跟 redirect；HTTPError=4xx/5xx 走 DOWN）
            with urllib.request.urlopen(result["target"], timeout=TIMEOUT_S) as resp:
                code = getattr(resp, "status", None) or resp.getcode()
                result["up"] = 200 <= code < 400
        elif stype == "tcp":
            # §4.2 socket connect 成功 → UP
            with socket.create_connection((server["host"], int(server["port"])), timeout=TIMEOUT_S):
                result["up"] = True
        elif stype == "ping":
            # §4.3 系統 ICMP；延遲取 time=，解析不到以子程序總耗時近似
            proc = subprocess.run(
                ping_command(server["host"]),
                capture_output=True, text=True, timeout=TIMEOUT_S,
            )
            result["up"] = proc.returncode == 0
            if result["up"]:
                match = RTT_RE.search(proc.stdout or "")
                result["rtt_ms"] = (
                    round(float(match.group(1)), 2) if match
                    else round((time.perf_counter() - t0) * 1000, 2)
                )
        if result["up"] and result["rtt_ms"] is None and stype in ("http", "https", "tcp"):
            result["rtt_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    except Exception:  # noqa: BLE001 — §4 timeout/例外一律 DOWN
        pass
    return result


def probe_all(servers):
    """§4 ThreadPoolExecutor 平行跑全部探測。"""
    if not servers:
        return []
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(servers))) as pool:
        return list(pool.map(probe, servers))


# ---------- HTTP handler ----------
class DashboardHandler(SimpleHTTPRequestHandler):
    """/api/status + 靜檔同 port 同源；CSV/API 停用快取方便熱改清單。"""

    def do_GET(self):  # noqa: N802 (http.server naming)
        if self.path.split("?")[0] == API_STATUS:
            self.handle_status()
            return
        super().do_GET()

    def handle_status(self):
        try:
            servers, problems = load_servers()
            results = probe_all(servers)
            for msg in problems:  # 無效列以 DOWN 條目呈現，清單上可見
                results.append({
                    "name": f"(跳過列) {msg.split('：', 1)[0]}", "type": "unknown",
                    "target": msg.split("：", 1)[1] if "：" in msg else msg,
                    "up": False, "rtt_ms": None,
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                })
            self.send_json(200, results)
        except FileNotFoundError:
            self.send_json(500, {"error": f"{CSV_PATH} 不存在（應與 server.py 同目錄）"})
        except ValueError as err:
            self.send_json(500, {"error": str(err)})
        except Exception as err:  # noqa: BLE001
            self.send_json(500, {"error": f"{type(err).__name__}: {err}"})

    def send_json(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):  # noqa: N802
        if self.path.endswith(".csv") or self.path.startswith(API_STATUS):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    handler = partial(DashboardHandler, directory=os.path.dirname(os.path.abspath(__file__)) or ".")
    httpd = ThreadingHTTPServer(("", port), handler)
    print(f"Dashboard: http://localhost:{port}/  (API: {API_STATUS})", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
