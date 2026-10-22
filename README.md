# SERVER STATUS MATRIX // 在線檢查

[English](README.md) | [繁體中文](README.zh-TW.md)

A zero-dependency server uptime dashboard: a single Python stdlib backend plus a single-file Matrix-style frontend. Watch your servers come alive in a wall of fluorescent green. (◕‿◕)

## Features

- **Zero dependencies** — backend is pure Python 3 stdlib (`http.server` + `urllib` + `socket` + `subprocess`); frontend is one `index.html` with no build step, no CDN, no framework.
- **CSV-driven inventory** — edit `servers.csv`, no restart needed (CSV and API responses are served with `Cache-Control: no-store`).
- **Four probe types**:
  | Type | Method | UP when |
  |------|--------|---------|
  | `http` / `https` | `urllib.request.urlopen` (follows redirects) | HTTP status 2xx/3xx |
  | `tcp` | `socket.create_connection` | TCP connect succeeds |
  | `ping` | system `ping` (ICMP, platform-adapted: Windows / macOS / Linux) | exit code 0 |
- **Parallel probing** — `ThreadPoolExecutor` (up to 32 workers), 2-second timeout per probe; any timeout/exception counts as DOWN.
- **RTT measurement** — HTTP/TCP measured around the request; ping parses `time=` from output (falls back to subprocess wall time).
- **Live dashboard** — auto-refresh every 5 s (plus manual `[ REFRESH ]`), UP/DOWN counts, per-server latency, and a terminal-style **event log** that derives UP↔DOWN transitions by diffing consecutive polls.
- **Matrix aesthetic** — dark background, fluorescent green, matrix character rain, CRT scanlines, glowing panels, monospace terminal font.

## Quick start

```bash
python3 server.py          # default port 8000
python3 server.py 9000     # custom port
```

Open <http://localhost:8000/>. Requires Python 3.8+; nothing to install.

## Configuration — `servers.csv`

```csv
name,type,host,port
PC1,http,192.168.0.11,80
PC2,https,192.168.0.12,443
FileServer,tcp,192.168.0.13,5001
VM1,ping,192.168.0.14,
```

- Required columns: `name`, `type`, `host`. `port` is required for `http`/`https`/`tcp`, ignored by `ping`.
- `type` ∈ `http` | `https` | `tcp` | `ping` (case-insensitive).
- Blank lines and lines starting with `#` are ignored.
- Invalid rows are skipped and shown as DOWN entries labeled `(跳過列) …` in the dashboard, so mistakes are visible instead of silently dropped.

## API

### `GET /api/status`

Runs all probes in parallel and returns a JSON array (or `{"error": ...}` with HTTP 500 on CSV problems):

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

All other paths are served as static files from the project directory (same port, same origin — no CORS setup).

## Project layout

```
server_dashboard/
├── server.py     # stdlib HTTP server: /api/status + static files
├── servers.csv   # server inventory (edit freely, hot-reloaded)
└── index.html    # Matrix-style frontend (fetches /api/status every 5 s)
```

## Notes & limitations

- Designed for LAN/self-hosted monitoring; probes run from the machine hosting `server.py`.
- Invalid CSV rows are reported as DOWN entries; missing/short-of-required-columns CSV returns HTTP 500 with an error message.
- Ping uses the OS `ping` binary; on macOS BSD ping, `-t 2` caps total seconds.

## License

MIT — see [LICENSE](LICENSE).
