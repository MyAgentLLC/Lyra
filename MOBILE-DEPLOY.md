# Deploying Lyra on an Android Phone (Termux)

Runs Lyra **fully on-device** — the LLM, the agent loop, and the command center all live on your phone. No cloud, no root required.

Tested target: Samsung Galaxy S26 Ultra (Snapragon 8 Gen 4, 12–16 GB RAM). Works on any modern Android with 6 GB+ RAM.

## What works on Android vs desktop

| Capability | Android | Notes |
|---|---|---|
| Local LLM (Ollama) | ✅ | Small models only — `qwen2.5:1.5b`, `llama3.2:1b` |
| Command center (web UI) | ✅ | Open `http://127.0.0.1:8420` in your phone browser |
| Shell commands on device | ✅ | Runs in Termux environment |
| Filesystem tools | ✅ | Termux home + shared storage (after `termux-setup-storage`) |
| Phone control (ADB) | ✅ | The agent can drive **this phone** via wireless ADB |
| Webhooks | ✅ | Local only by default |
| Plugins | ✅ | Same plugin system |
| Desktop GUI control (pyautogui) | ❌ | No display server on Android — calls return a clear error, agent keeps working |
| Browser automation (Playwright) | ❌ | Chromium can't run inside Termux — disabled in mobile config |
| **Phone-native skills (Termux:API)** | ✅ | Notifications, TTS voice, clipboard, battery, location, flashlight, volume, wifi |
| **Web skills** | ✅ | web_search (DDG→Bing fallback), fetch_url, download_file |
| **Personal kit** | ✅ | Calculator, notes, reminders, todos — stored locally in data/personal/ |

For full computer + browser control, run Lyra on your laptop and access it from the phone over Tailscale (see [DEPLOY.md](DEPLOY.md)).

---

## Step-by-step install (on the phone)

### 1. Install Termux (NOT from Play Store)

The Play Store build is outdated and breaks installs. Get the F-Droid/GitHub build:

- Download: https://github.com/termux/termux-app/releases (latest `termux-app_..._arm64-v8a.apk`)
- Or install F-Droid, then Termux from it: https://f-droid.org
- Sideload the APK (allow "install unknown apps" when prompted)

### 2. Get the code

Open Termux and run:

```bash
pkg update -y && pkg install -y git
git clone https://github.com/MyAgentLLC/Lyra.git
cd Lyra
```

### 3. Run the installer

```bash
bash termux-setup.sh
```

This installs Python, Ollama, a small model (~1 GB), and all dependencies. Takes 5–15 minutes depending on connection.

### 4. Start the agent

```bash
termux-wake-lock          # keeps Android from killing the process
python run.py --config config/config.mobile.yaml
```

### 5. Open the command center

In Chrome/Samsung Internet on the same phone:

```
http://127.0.0.1:8420
```

You now have the full Lyra dashboard running locally.

> **The dashboard is locked.** The first time you open it you'll land on a
> sign-in page asking for your dashboard token.
>
> - **First run:** Lyra auto-generates a strong token and saves it to
>   `~/Lyra/data/.api_token` (readable only by you, never committed to git).
>   Open that file, copy the token, paste it on the sign-in page. Your browser
>   stays signed in for 30 days.
> - **Your own token:** set `LYRA_API_TOKEN` before starting, or uncomment
>   `api_token:` under `server:` in `config/config.mobile.yaml`.
> - **Scripts/API:** send `Authorization: Bearer <token>` or append
>   `?token=<token>` — e.g. `curl -H "Authorization: Bearer $TOKEN"
>   http://127.0.0.1:8420/api/status`.
> - **Forgot it?** Delete `~/Lyra/data/.api_token` and restart — a fresh token
>   is generated.
>
> Incoming webhooks (`/webhook/<name>`) stay reachable without the dashboard
> token — they use their own per-webhook secrets.

---

## Day-to-day usage

**Start (each session):**
```bash
cd ~/Lyra
nohup ollama serve > ~/ollama.log 2>&1 &   # if not already running
termux-wake-lock
python run.py --config config/config.mobile.yaml
```

**Stop:** tap `Ctrl+C` (volume-down + C in Termux), then `termux-wake-unlock`.

**Keep it alive:** Settings → Apps → Termux → Battery → Unrestricted. Android aggressively kills background processes otherwise.

**Access phone storage** (so the agent can read/write your Downloads etc.):
```bash
termux-setup-storage
```

---

## Optional: agent controls its own phone

The agent can tap, swipe, screenshot, and open apps on **this** phone via ADB, no cable needed:

1. Settings → About phone → tap Build number 7× (enables Developer options)
2. Developer options → **Wireless debugging** → On
3. In Termux:
```bash
pkg install -y android-tools
adb pair 127.0.0.1:<pairing-port>     # port shown under "Pair device with pairing code"
adb connect 127.0.0.1:<connect-port>  # port shown under "Wireless debugging"
adb devices                            # should list the phone
```
4. Restart Lyra — the `phone_*` tools now control the phone itself.

The wireless-debugging port changes on reboot; re-run `adb connect` if tools report no device.

---

## Keeping Lyra alive + chatting without a browser (v2.2)

### Why the connection dies when you switch apps
Android kills background processes aggressively — that takes down the Ollama server
and/or the command center, and the browser page loses connection. Three settings fix it:

1. **Wake lock** — `bash lyra.sh start` acquires it automatically (`termux-wake-lock`).
2. **Battery optimization** — Android Settings → Apps → Termux → Battery → **Unrestricted**.
   On Samsung also: Settings → Battery → Background usage limits → make sure Termux is
   never put to sleep, and turn off "Remove permissions if app unused" for Termux.
3. **Phantom process killer** (Android 12+; needed when Ollama still dies in background):
   - Enable Developer options → Wireless debugging (phone Settings)
   - In Termux:
     ```
     adb start-server
     ```
   - Pair once from the wireless-debugging screen (`adb pair ip:port` with the pairing code),
     then connect (`adb connect ip:port`), then run:
     ```
     adb shell device_config put activity_manager max_phantom_processes 2147483647
     ```
   - This tells Android to stop killing Termux child processes in the background. Reboot-safe
     on most builds; if Ollama dies again after a phone reboot, rerun that one command.

### Talking to Lyra without the browser
- **Terminal chat** — `bash lyra.sh chat` (or `python chat.py`): full agent with tools,
  right in Termux. Commands inside: /help /tools /status /reset /exit.
- **Command center** — `bash lyra.sh start`, then http://127.0.0.1:8420 in Chrome.

### lyra.sh — one command for everything
| Command | What it does |
|---|---|
| `bash lyra.sh start` | wake lock + starts Ollama + command center (both stay running) |
| `bash lyra.sh stop` | stops both, releases wake lock |
| `bash lyra.sh restart` | one-command recovery after Android killed things |
| `bash lyra.sh chat` | terminal chat with Lyra (tools included) |
| `bash lyra.sh status` | shows whether Ollama / command center are up |
| `bash lyra.sh log` | follow the server log |

If she ever "stops responding": `bash lyra.sh restart` — that's it.

## Setup notes (v2.1.1)

- The Python deps step installs the **Rust toolchain** (~400 MB, one-time) because
  FastAPI's pydantic-core has no prebuilt Android wheel — it compiles on your phone
  the first time (5–15 min). Later runs skip it.
- On Termux, never run `pip install --upgrade pip` — it corrupts the python-pip package.
- Deps are intentionally unpinned: pinned versions may not compile on Termux Python 3.14.

## Lyra's skill set (v2.1)

Lyra ships with three skill plugins (auto-loaded from `plugins/`):

| Plugin | Skills |
|---|---|
| `phone_native` | phone_notify, phone_speak (TTS), clipboard get/set, battery, location, flashlight, volume, wifi info, device info |
| `web_tools` | web_search (DuckDuckGo with Bing fallback), fetch_url, download_file |
| `personal_kit` | calculator, notes (add/read/list), reminders (add/list/done), todos (add/list/done) |

Phone-native skills need one extra piece (already installed by `termux-setup.sh`):
the **Termux:API app** from F-Droid — `pkg install termux-api` handles the CLI side.
Install the companion app from https://f-droid.org/packages/com.termux.api/ and grant
the notification permission on first use.

Skills only make network calls when you ask for something that needs them
(fetch a page, search the web). Nothing phones home on its own.

Adding more skills: drop a folder in `plugins/` with a `plugin.json` and `plugin.py`
— see `plugins/example/` for the template.

## Model notes

| Model | Size | RAM needed | Speed on S26 Ultra |
|---|---|---|---|
| `qwen2.5:1.5b` | ~1 GB | ~2.5 GB | Fast, decent tool calling |
| `llama3.2:1b` | ~1.3 GB | ~2 GB | Fastest, simpler |
| `llama3.2:3b` | ~2 GB | ~4 GB | Slower, smarter |
| `qwen2.5:3b` | ~2 GB | ~4 GB | Best quality that stays responsive |

Switch by editing `model.name` in `config/config.mobile.yaml` and running `ollama pull <model>`.

Phone models are much weaker than laptop ones — expect simpler reasoning, shorter plans, and occasional tool-call mistakes vs the 7B/8B laptop models.

---

## Troubleshooting

**"Ollama connection refused"** — start it: `ollama serve &` (check `~/ollama.log`)

**pip build errors for aiohttp** — `pkg install -y binutils` then retry, or `pip install --no-binary :none: aiohttp`... if a wheel isn't available for Android, `pip install aiohttp` builds from source with the clang installed by the setup script.

**App killed in background** — disable battery optimization for Termux, use `termux-wake-lock`, keep Termux in the foreground or in the recents-locked list.

**"NewYork (connection lost)" from Termux** — Android's phantom process killer; run `termux-wake-lock`, and Settings → Battery → unrestricted.

**Killed with exit 137 / OOM** — model too big; use a smaller one (1B).

**Port 8420 busy** — `pkill -f run.py` then restart.
