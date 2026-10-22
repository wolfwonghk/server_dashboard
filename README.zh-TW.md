# SERVER STATUS MATRIX // 在線檢查

[English](README.md) | [繁體中文](README.zh-TW.md)

零依賴的伺服器在線檢查 Dashboard：一支純 Python 標準函式庫後端，加上一支單檔 Matrix 風前端。讓你的伺服器狀態在螢光綠的字符雨中活過來 (◕‿◕)

## 功能特色

- **零依賴** — 後端是純 Python 3 標準函式庫（`http.server` + `urllib` + `socket` + `subprocess`）；前端是一支 `index.html`，免 build、免 CDN、免框架。
- **CSV 驅動清單** — 直接改 `servers.csv` 即生效，不用重啟（CSV 與 API 回應都带 `Cache-Control: no-store`）。
- **四種探測型別**：
  | 型別 | 方式 | 判定 UP 條件 |
  |------|------|--------------|
  | `http` / `https` | `urllib.request.urlopen`（自動跟 redirect） | HTTP 狀態碼 2xx/3xx |
  | `tcp` | `socket.create_connection` | TCP connect 成功 |
  | `ping` | 系統 `ping`（ICMP，依平台適配 Windows / macOS / Linux） | 結束碼 0 |
- **平行探測** — `ThreadPoolExecutor`（最多 32 workers），每個探測 2 秒 timeout；timeout/例外一律判定 DOWN。
- **延遲量測** — HTTP/TCP 以請求前後計時；ping 解析輸出中的 `time=`（解析不到時以子程序總耗時近似）。
- **即時面板** — 每 5 秒自動刷新（另有手動 `[ REFRESH ]` 按鈕）、UP/DOWN 計數、各伺服器延遲，以及終端機風**事件日誌**：比對前後兩輪 up 狀態推導 UP↔DOWN 狀態變更。
- **Matrix 美學** — 深黑底、螢光綠、字符雨、CRT 掃描線、發光面板、終端機等寬字型。

## 快速開始

```bash
python3 server.py          # 預設 port 8000
python3 server.py 9000     # 自訂 port
```

瀏覽器開啟 <http://localhost:8000/>。需要 Python 3.8+，免安裝任何套件。

## 設定 — `servers.csv`

```csv
name,type,host,port
PC1,http,192.168.0.11,80
PC2,https,192.168.0.12,443
FileServer,tcp,192.168.0.13,5001
VM1,ping,192.168.0.14,
```

- 必要欄位：`name`、`type`、`host`。`port` 對 `http`/`https`/`tcp` 為必要，`ping` 會忽略它。
- `type` ∈ `http` | `https` | `tcp` | `ping`（大小寫不拘）。
- 空行與 `#` 開頭的註解行會被忽略。
- 無效列會被跳過，並在面板上以 `(跳過列) …` 的 DOWN 條目呈現，錯誤看得见、不會無聲消失。

## API

### `GET /api/status`

平行跑完所有探測後回傳 JSON 陣列（CSV 有問題時回 HTTP 500 + `{"error": ...}`）：

```json
[
  {
    "name": "PC1",
    "type": "http",
    "target": "http://192.168.0.11:80",
    "up": true,
    "rtt_ms": 3.42,
    "checked_at": "2026-10-22T11:00:00.000000+00:00"
  }
]
```

其餘路徑一律以專案目錄為根做靜態檔案服務（同 port、同源，免設 CORS）。

## 專案結構

```
server_dashboard/
├── server.py     # 標準函式庫 HTTP server：/api/status + 靜態檔案
├── servers.csv   # 伺服器清單（隨時可改，熱生效）
└── index.html    # Matrix 風前端（每 5 秒 fetch /api/status）
```

## 注意事項與限制

- 定位為 LAN／自架監控；探測從跑 `server.py` 的那台機器發起。
- 無效 CSV 列會以 DOWN 條目呈現；CSV 檔案缺失或缺必要欄位時回 HTTP 500 與錯誤訊息。
- ping 使用作業系統的 `ping` 執行檔；macOS BSD ping 以 `-t 2` 限制總秒數。

## 授權

MIT — 詳見 [LICENSE](LICENSE)。
