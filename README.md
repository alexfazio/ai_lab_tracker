<a href="https://x.com/alxfazio" target="_blank">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="images/firecrawl-devdocs-to-llm-cover.png">
    <img alt="OpenAI Cookbook Logo" src="images/ai-lab-tracker-GitHub-banner.jpg" width="400px" style="max-width: 100%; margin-bottom: 20px;">
  </picture>
</a>

# AI Lab Tracker

A fully‑asynchronous Python 3.11 application that watches AI‑related websites, blogs and documentation pages, detects content changes with [Firecrawl Change‑Tracking](https://docs.firecrawl.dev/features/change-tracking), lets an [OpenAI Agent](https://openai.github.io/openai-agents-python/) decide whether the diff is **news‑worthy**, and then sends concise Telegram notifications.

---

## ✨ Features

| Component | Tech | Purpose |
|-----------|------|---------|
| **Crawling / Diff** | Firecrawl `/scrape` & `/crawl` | Retrieves markdown + git‑style diff for each source URL |
| **Relevance filter** | OpenAI Agents SDK | Evaluates each diff, returns `{relevant: bool, summary: str}` |
| **Notification** | python‑telegram‑bot v21 | Sends Rich‑formatted messages (title, summary, diff snippet, link) |
| **Logging** | `logging` + RichHandler | Colorful console logs & optional Telegram log forwarder |
| **Scheduler** | GitHub Actions cron | Runs every 10 minutes by default (`.github/workflows/change-tracker.yml`) |

---

## 🚀 Quick Start (Local)

### 1 Clone & enter the repo
```bash
git clone https://github.com/yourname/ai_lab_tracker.git
cd ai_lab_tracker
```

### 2 Create/activate Python 3.11 env
```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

### 3 Install deps (editable)
```bash
pip install --upgrade pip
pip install -e .
```

### 4 Create a `.env` file
```env
FIRECRAWL_API_KEY = fc‑********************************
OPENAI_API_KEY    = sk‑********************************
TELEGRAM_BOT_TOKEN= ********************************
TELEGRAM_CHAT_IDS = -***********  # comma‑separated for multiple chats
# Optional
LOG_LEVEL         = DEBUG           # DEBUG / INFO / WARNING / …
TELEGRAM_SEND_LOGS= true            # forward logs to Telegram
```

### 5 Run once
```bash
python -m ai_lab_tracker.cli
```
The tracker will:
1. Load YAML source files from `sources/`.
2. Fetch/crawl pages via Firecrawl.
3. Pass every non‑identical diff to the OpenAI Agent.
4. Send Telegram messages for relevant updates.

---

## 🧪 Testing without real site updates

Use the built‑in **dummy notifier** to generate fake diffs and exercise the full path:

```bash
# Dry‑run (no Telegram message)
python -m ai_lab_tracker.dummy_notify --force relevant

# Send a real Telegram test message
python -m ai_lab_tracker.dummy_notify --send --force relevant
```
`--force relevant|irrelevant` monkey‑patches the agent so you can verify that:
* relevant → notification is sent
* irrelevant → nothing is sent

---

## 🔧 Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `FIRECRAWL_API_KEY` | – | Required Firecrawl key |
| `OPENAI_API_KEY` | – | Required OpenAI key |
| `OPENAI_MODEL` | `gpt-4.1` | Model passed to agent factory |
| `FIRECRAWL_RATE_LIMIT_PER_MINUTE` | `5` | Local sliding‑window limit |
| `TELEGRAM_BOT_TOKEN` | – | Bot to send messages |
| `TELEGRAM_CHAT_IDS` | – | Comma‑separated chat IDs |
| `TELEGRAM_SEND_LOGS` | `false` | Forward logs to Telegram |
| `LOG_LEVEL` | `INFO` | Root log level (DEBUG recommended locally) |

Sources are plain YAML files under `sources/`. Add/disable by editing or adding new files:
```yaml
name: Awesome AI Blog
url: https://awesome.ai/blog
mode: GitDiff
cadence: "*/30 * * * *"  # every 30 min
labels: [awesome, blog]
enabled: true
```


---

## 🏗️ CI / GitHub Actions
GitHub workflow `.github/workflows/change-tracker.yml` installs the package and runs the tracker on `cron: '*/10 * * * *'`. Store your secrets in **repo settings → Secrets → Actions**:
```
FIRECRAWL_API_KEY
OPENAI_API_KEY
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_IDS
```

---

## 🖥️ Logging
* Rich console output via `RichHandler` (colors, timestamps).  
* Set `LOG_LEVEL=DEBUG` for verbose output.  
* If `TELEGRAM_SEND_LOGS=true`, logs < INFO are sent to your chat using `TelegramLogHandler`.

---

## 🤝 Contributing
Pull requests welcome!  Please follow PEP 8, include type hints, and keep logging consistent with the [Rich Styling Guide](./rich-library.mdc).

---

## 📜 License
MIT License.  See `LICENSE` file for details.

---

## 🙏 Credits
Built with [Firecrawl‑py](https://pypi.org/project/firecrawl-py/), [openai‑agents‑python](https://github.com/openai/openai-agents-python), [python‑telegram‑bot](https://python-telegram-bot.org/), and [Rich](https://rich.readthedocs.io/). 
