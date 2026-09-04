# 🌙 LUNA Desktop

**LUNA is a local-first AI desktop personal assistant and general-purpose
computer-use agent for Windows.**

LUNA is not a chatbot and not a macro recorder. You give it a goal; it plans,
picks tools from a generic automation layer, executes, **observes and verifies
each result**, adapts when a UI changes, asks permission before high-impact
actions, and reports an honest outcome.

- Dark-first, lunar, premium Qt interface (PySide6)
- Persistent task system (SQLite + JSON artifacts) that keeps running while LUNA is in the tray
- General browser automation (Playwright) — no `youtube.py`, no `fiverr.py`
- Windows desktop automation (UI Automation + keyboard/mouse fallback)
- File system + controlled terminal tools (capture, exit codes, cancellation, permission-gated)
- AI provider abstraction (Ollama local by default; OpenAI-compatible APIs; llama.cpp)
- Local Model Manager (import / validate / detect / select / test / remove — models never in Git)
- **Kokoro TTS** that supports exactly `model_q8f16.onnx` and `model_fp16.onnx`, voice `.bin` assets, and a real **Test Voice** button (no cloud TTS, no system TTS)
- Local SQLite memory with search / delete / clear / disable
- Configurable personality system, permissions, notifications, tray background operation
- GitHub Actions: tests on Linux + full tests and **Windows .exe build** with artifact upload

---

## Quick start (Windows)

```powershell
git clone https://github.com/seyon-ai/Luna_Desktop.git
cd Luna_Desktop
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[all]"
python -m playwright install chromium   # or use installed Edge/Chrome
python -m luna
```

If you only want the core (no optional AI/voice extras):

```powershell
pip install -e .            # core
pip install -e ".[ui]"      # + Qt UI
pip install -e ".[ai]"      # + Ollama/API provider client
pip install -e ".[browser]" # + Playwright
pip install -e ".[tts]"     # + Kokoro
pip install -e ".[desktop]" # + desktop automation
```

### Import models and voices (through the UI)

1. Open **Models → Import Model** and pick a local model (ONNX / GGUF / safetensors).
2. For Kokoro, import **exactly** `model_q8f16.onnx` or `model_fp16.onnx`
   (do not rename them; LUNA rejects renamed Kokoro files by design).
3. Open **Voice → Import Voice (.bin)** and choose a Kokoro voice asset
   (e.g. `af_heart.bin`, `am_michael.bin`).
4. Press **Test Voice**. LUNA synthesizes with the real Kokoro ONNX graph and
   plays the resulting WAV. If the model or runtime is missing, it reports the
   exact missing dependency instead of faking audio.

No AI/Kokoro model files are committed to Git — they are user-provided at
`LUNA_HOME/models/` and `LUNA_HOME/voices/`.

---

## LUNA_HOME

All user data lives outside the Git repository:

| Windows default | `%LOCALAPPDATA%\Luna` |
|---|---|
| Linux/macOS default | `~/.luna` |

Override with the `LUNA_HOME` environment variable.

```text
LUNA_HOME/
├── models/                 # imported models (LLM + Kokoro ONNX)
├── voices/                 # imported Kokoro voice .bin assets
├── memory/luna.db          # conversations, preferences, memories (SQLite)
├── tasks/                  # task JSON artifacts + DB rows
├── logs/                   # command logs, runtime logs
├── cache/browser-profile/  # Playwright persistent profile
└── config/config.json      # all application settings
```

---

## Core loop

```text
USER GOAL
  → UNDERSTAND (planner + AI)
  → SELECT TOOLS (generic registry)
  → EXECUTE (browser / desktop / filesystem / terminal)
  → OBSERVE (read page, accessibility tree, screenshot, stdout)
  → VERIFY (expected state; if changed → re-observe → adapt)
  → CONTINUE / RECOVER / ASK USER
  → RESULT
```

Every action that can’t be verified is reported as a limitation — LUNA never
pretends a click or a task succeeded.

## Generic automation (no site-specific modules)

- **Browser**: navigate, tabs, page text, find by CSS/role/name/placeholder,
  click, type, press, scroll, wait, screenshot, extract — composed generically
  by the AI. YouTube search is just `navigate → find searchbox → type → Enter →
  read results`.
- **Desktop (Windows)**: launch/close apps, focus/minimize/maximize windows,
  accessibility tree reading, click, double-click-capable input path, type,
  hotkeys, scroll, screenshot, clipboard copy/paste.
- **Filesystem**: list/read/create/append/move/delete/search/organize inside a scoped workspace.
- **Terminal**: subprocess with stdout/stderr capture, exit status, timeouts,
  cancellation, command logging and a permission rule (`run_command`).

## Permissions

Rules are configured in **Settings → Permissions**: `allow` / `ask` / `deny`.

| Action | Default |
|---|---|
| Read files, list dirs, create files, modify files | allow |
| Delete files, move files, run commands, system config, desktop control | ask |
| Send external messages, submit forms | ask |
| Purchases | deny |

There is no silent external communication: the agent prepares drafts, then
asks the user before sending.

## AI providers

| Provider | Local | Tools | Default |
|---|---|---|---|
| `ollama` | ✅ | ✅ | yes (`http://127.0.0.1:11434`, model configurable) |
| `openai_compatible` | optional | ✅ | via env-var key, never stored in source |
| `llama_cpp` | ✅ | text only | via configured `.gguf` path |

Add a new provider by implementing `AIProvider` (`luna/ai/providers/base.py`)
and registering it in `luna/ai/providers/registry.py`.

## Personality

Settings → Personality: Professional / Friendly / Friendly Companion / Concise /
Custom, with tone, verbosity, conversational style, friendliness and response
format. The generated guidance is injected into the agent's system prompt.

## Testing

```bash
pip install -e ".[dev]"
pytest tests -q
```

Covers configuration, LUNA_HOME, SQLite, memory, task lifecycle (pause/resume/
cancel/failure/persistence), model manager (Kokoro exact-name import, GGUF /
ONNX validation, remove), permissions, tool registry, file tools, terminal,
planner, personality, agent tool-call loop, cancellation and approval bridge.
Qt GUI smoke tests run on the Windows CI runner (or locally with
`LUNA_FORCE_UI_TESTS=1`).

## Building the Windows application

```bash
python scripts/build_windows.py
# → dist/LUNA/LUNA.exe
```

Or let GitHub Actions do it: pushes to `main`/`arena/**` run tests and build;
tagged releases (`v*`) upload a portable zip with `LUNA.exe`.

> The workflow is maintained at `build/github-actions/ci.yml` (reference copy)
> and `.github/workflows/ci.yml` (active copy). If your token cannot push
> files under `.github/workflows/` (GitHub App scope), activate it by copying
> the reference file into `.github/workflows/ci.yml` with an account/token
> that has the `workflows` scope — the pipeline itself is ready as-is.

## Repository layout

```text
luna/
├── app/           Application wiring + entry point
├── ai/
│   ├── providers/  Ollama, OpenAI-compatible, llama.cpp, adapters
│   └── model_manager/ import/validate/detect/select/test/remove
├── automation/
│   ├── browser/   Playwright generic workflow primitives
│   ├── desktop/   Windows UIA + input fallback
│   ├── filesystem.py
│   ├── terminal.py
│   └── tools/     registry of agent tools
├── config/        settings + LUNA_HOME layout
├── core/          agent loop, planner, tasks, permissions, tools, personality
├── storage/       SQLite (db + memory)
├── ui/            PySide6 dark lunar UI, tray, approval dialogs
├── voice/         Kokoro TTS, voice manager, STT, wake-word interface
└── assets/        generated original logo (SVG/PNG/ICO/tray/splash)
build/             PyInstaller spec
scripts/           asset generator, Windows build
tests/             real, runnable tests
.github/workflows/ CI + Windows package + release
```

## Security notes

- No API keys in source; keys come from environment variables named in settings.
- Models, voices, `*.db`, browser profiles, logs and build artifacts are git-ignored.
- Shell access is controlled (`run_command` = ask by default) and every command is logged.
- External messages are never sent silently; purchases are denied by default.
- Memory is local-only (SQLite). LUNA does not auto-store arbitrary private web content.

## Roadmap (explicitly designed-for, not faked)

- Voice pipeline: mic → wake word (replaceable engine) → STT → agent → Kokoro → speaker.
- "Research → spec → coding prompt → user approval → coding-agent handoff"
  self-development workflow (architecture-ready; no uncontrolled self-modification).
- Vision fallback for screenshots and multi-app task state orchestration.
