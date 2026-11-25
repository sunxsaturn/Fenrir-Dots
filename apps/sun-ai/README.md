# Sun AI — in-repository component

Sun AI is a first-party Fenrir Desktop component. Its complete Fenrir-authored application source is maintained in this repository; it is not a separate checkout, remote script, or post-install download.

## Source map

| Path | Responsibility |
|---|---|
| `apps/sun-ai/server.py` | Local HTTP dashboard server and Ollama API bridge |
| `apps/sun-ai/index.html` | Dashboard document |
| `apps/sun-ai/assets/app.js` | Browser application logic |
| `apps/sun-ai/assets/style.css` | Dashboard styling |
| `bin/sun-ai` | Start, stop, open, status and logs command |
| `systemd/user/sun-ai.service` | On-demand per-user service |
| `applications/sun-ai.desktop` | Application launcher |
| `config/icons/Fenrir-Obsidian/scalable/apps/sun-ai.svg` | Fenrir icon |
| `tests/test_sun_ai.py` | Security and behavior regression tests |

## Runtime boundary

- The dashboard binds to `127.0.0.1:8765`.
- Ollama is restricted to its local API at `127.0.0.1:11434`; the server refuses a non-local `OLLAMA_HOST`.
- Conversation history is stored locally in `~/.local/state/sun-ai/history.sqlite3`.
- User preferences are stored in `~/.config/sun-ai/settings.json`.
- Starting and stopping the model runtime is explicit. The user CLI tracks whether Sun AI started Ollama and avoids stopping an Ollama service that was already running beforehand.
- The service is not enabled for automatic login startup. This avoids competing with gaming and audio workloads.

## Dependencies

Fenrir-authored dashboard code uses the Python standard library. Ollama is a separately packaged local inference runtime installed by Fenrir-Arch when Sun AI is selected. A model is not downloaded automatically: the user chooses and downloads a model through Ollama.

Model weights and Ollama's runtime files are machine-local runtime data, not Fenrir application source. They are intentionally not copied into Git history as opaque multi-gigabyte artifacts; no model weights, tokens, conversation history or user settings are committed.

## Install path

Fenrir-Arch clones this repository as the companion desktop source, validates the Sun AI files, and installs these tracked paths:
- `apps/sun-ai/` to `~/.local/share/sun-ai/`
- `bin/sun-ai` to `~/.local/bin/sun-ai`
- `systemd/user/sun-ai.service` to `~/.config/systemd/user/sun-ai.service`
- `applications/sun-ai.desktop` to `~/.local/share/applications/sun-ai.desktop`
- The SVG under the Fenrir icon theme to `~/.local/share/icons/Fenrir-Obsidian/`

No Sun AI source is generated locally or downloaded from another repository during installation.

## Development

From the repository root:

```bash
python3 -m compileall -q apps/sun-ai tests
python3 -m unittest tests.test_sun_ai -v
bash -n bin/sun-ai
```
