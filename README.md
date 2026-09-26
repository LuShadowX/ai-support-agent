# AI Support Agent

An AI customer-support agent that **answers from your business documents** and **takes real actions**: it looks up orders, checks live stock and hands off to a human. Runs as a one-line website chat widget and as a Telegram bot.

**Live demo:** https://ai-support-agent-tbk8.onrender.com (free hosting, so the first load can take ~50s)

## Features
- **Answers from your data (RAG):** PDFs, Markdown/text files and web pages. It only answers from your content and says "I don't know" instead of making things up.
- **Takes actions (tool calling):** order status and tracking (verified by order ID + email), live price and stock, and support tickets for human handoff.
- **Works on any website:** one `<script>` tag. The widget uses Shadow DOM so it never clashes with the site's CSS, and it's mobile friendly.
- **Telegram channel:** same brain, same knowledge base.
- **Any LLM:** OpenRouter, Gemini, OpenAI, Groq. Switch with one env variable.
- **Free local embeddings:** no per-document API cost.
- **Production basics:** rate limiting, input limits, CORS allow-list, chat history, graceful LLM-failure handling, Docker.

## Architecture
```
Website widget ─┐                     ┌─> search_knowledge_base ─> ChromaDB (your docs)
                ├─> FastAPI /api/chat ─> Agent loop (LLM) ─┼─> lookup_order / check_product ─> SQLite (or client's API)
Telegram bot ───┘                     └─> create_support_ticket ─> tickets table
```

## Quick start
```bash
uv sync                                  # install
cp .env.example .env                     # then add your LLM_API_KEY
uv run python -m app.ingest              # index data/docs/
uv run uvicorn app.main:app --reload     # open http://localhost:8000
```
Try:
- "What's your return policy?"
- "Where is order NH-1001? Email priya@example.com"
- "Is the throw blanket in stock?"
- "I want to talk to a human"

### Add your own content
Drop PDFs, `.md` or `.txt` files into `data/docs/`, or index web pages:
```bash
uv run python -m app.ingest --url https://example.com/faq --url https://example.com/shipping
```

### Telegram
Create a bot with [@BotFather](https://t.me/BotFather), set `TELEGRAM_BOT_TOKEN` in `.env`, then:
```bash
uv run python -m app.telegram_bot
```

### Embed on any website
```html
<script src="https://YOUR-SERVER/static/widget.js" data-color="#2f5d50" defer></script>
```
Set `ALLOWED_ORIGINS=["https://your-site.com"]` in production.

### Docker
```bash
docker build -t support-agent .
docker run -p 8000:8000 --env-file .env -v $(pwd)/storage:/app/storage support-agent
```

## API
| Method | Path | Description |
|---|---|---|
| POST | `/api/chat` | `{"message": "...", "session_id": "optional"}` → `{session_id, reply, sources}` |
| GET | `/api/config` | Bot name and greeting (used by the widget) |
| GET | `/api/health` | Status and number of indexed documents |
| GET | `/api/tickets` | Handoff tickets. Needs the `X-Admin-Token` header (set `ADMIN_TOKEN`) |

## Project layout
```
app/
  config.py        settings from .env
  knowledge.py     load → chunk → embed → store → search
  tools.py         tools the agent can call (add client-specific ones here)
  agent.py         system prompt + tool-calling loop
  db.py            SQLite: orders, products, tickets, chat history
  main.py          FastAPI server
  ingest.py        CLI to index documents
  telegram_bot.py  Telegram channel
static/            widget.js + demo store page
data/docs/         the knowledge base source files
```

## Customising for a client
1. Replace `data/docs/` with their content, then run `ingest --reset`.
2. Set `BUSINESS_NAME`, `BOT_NAME` and the widget `data-color`.
3. Point `db.get_order` and `db.find_products` at their real system (Shopify, WooCommerce, CRM or API).
4. Edit the rules in `SYSTEM_PROMPT` (`app/agent.py`).
