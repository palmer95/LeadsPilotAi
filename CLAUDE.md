# LeadsPilotAI — Project Notes for Claude

## What This Is
Multi-tenant AI sales chatbot SaaS. Clients get a `<script>` tag that embeds a branded chatbot on their site. Current clients: Virtour Media, LeadsPilotAI (own site).

## Repos
- `product/` — this repo (backend Flask API + React frontend widget)
- `leadspilotai-site/` — Next.js marketing/admin site, serves `public/chatbot.js` and `public/client-configs/{slug}.json`

## Stack
- **Backend**: Python/Flask, LangChain, OpenAI (GPT + embeddings), FAISS, MongoDB Atlas
- **Frontend widget**: React, bundled with Parcel via `npm run build:widget` in `frontend/`
- **Auth**: JWT for admin dashboard, API key for onboarding endpoint
- **Hosting**: Render (backend API) — considering migration to Railway this week

## Key Commands
- Rebuild widget after frontend changes: `cd frontend && npm run build:widget`
  - Outputs to `../../leadspilotai-site/public/chatbot.js`
  - Must push `leadspilotai-site` repo after rebuilding for changes to go live
- Run backend locally: activate `.venv` then `python backend/app.py`

## Architecture Notes
- Each client has a slug (e.g. `virtour`, `leadspilotai`)
- Client config JSON lives at `leadspilotai.com/client-configs/{slug}.json`
- FAISS vectorstores committed to git at `backend/vectorstores/{slug}_vectorstore/`
- Custom training data stored in MongoDB `custom_training` collection
- In-memory session state (`_session_memory` in `core.py`) — lost on restart, breaks with multiple gunicorn workers
- All shared DB/LLM objects should come from `core.py` (some modules still create their own MongoClient — technical debt)

## Rebuild & Deploy Flow
1. Edit frontend → `npm run build:widget` → push `leadspilotai-site`
2. Edit backend → push `product` → Render auto-deploys

---

## Pending Upgrades (prioritized)

### High Priority
- [ ] **Migrate backend to Railway** — Render removed Starter plan, now on Pro ($25/mo). Railway is cheaper and has better logs. Do this week.
- [ ] **Fix in-memory session state** — `_session_memory` in `core.py` is a plain dict. Lost on restart, broken across gunicorn workers. Replace with MongoDB-backed session storage.
- [x] **Consolidate MongoClient instances** — Done. All modules now import collections from `core.py`. `mongo_db.py` is a dead file (nothing imports it) and can be deleted.
- [ ] **Add rate limiting to `/api/chat`** — No protection against spam/abuse driving up OpenAI costs. Add Flask-Limiter.

### Medium Priority
- [ ] **Switch LLM to Claude** — User prefers Claude. Keep OpenAI for embeddings only (FAISS already built with them). Use `langchain-anthropic` + `claude-sonnet-4-6`.
- [ ] **Invalidate priority vectorstore cache on training data changes** — Currently cached forever in `_vectorstore_cache`. When admin adds/deletes training data, the cache is stale until restart. Clear `{slug}_priority_vs` from cache on write in `training_routes.py`.
- [ ] **Input length validation on `/api/chat`** — No max length check on user queries. Add a guard (e.g. 2000 chars) before hitting OpenAI.

### Low Priority
- [ ] **Replace `datetime.utcnow()`** — Deprecated in Python 3.12+. Use `datetime.now(timezone.utc)` throughout.
- [ ] **Environment variable for API base URL in frontend** — `API_BASE_URL` is hardcoded in `frontend/src/App.js`. Use `process.env.REACT_APP_API_URL`.
- [ ] **Re-embed vectorstores for new clients** — `clean_and_embed.py` still has hardcoded Virtour URLs. Make it fully driven by `COMPANY_SLUG` env var and a client config file so new clients can be embedded without editing code.
