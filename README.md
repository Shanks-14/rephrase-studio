# VerbaHumanize

An editorial-styled rephrasing studio: paste a paragraph, pick a rewrite mode (synonym, antonym, rhyme, syllable-flip, academic, conversational), and get a highlighted, word-by-word editable rewrite — plus AI-detection and plagiarism scoring, a live parts-of-speech breakdown, and a playful "Word Sandbox" for freeform word-cycling.

Built as a full-stack demo: **FastAPI** backend (all business logic in Python, LLM-optional with a deterministic offline fallback) + a **React** frontend (thin client — routing, forms, theming, and interaction only).

---

## ✨ Features

- **Rephrase Studio** — split-pane editor: paste text on the left, get a highlighted rewrite on the right. Six modes: synonym / antonym / rhyme / syllable-flip / academic / conversational.
- **Click-to-swap words** — click any highlighted word in the output to open a modal with alternative suggestions (or type your own), with one-click revert.
- **Live parts-of-speech breakdown** — nouns / verbs / adjectives / adverbs / prepositions, color-coded, updates as you type.
- **AI & Plagiarism scoring** — dual circular scorecards; gated behind sign-in.
- **Word Sandbox with Fan mode** — toggle "Fan mode" from the Rephrase Studio header to open a playful canvas where hovering a word rapidly cycles through alternatives; click a word to step through them manually. Turning Fan mode off closes the Sandbox again.
- **Auth** — email/password registration & login, JWT in an httpOnly cookie.
- **Guest mode** — up to 350 words without an account; unlimited when signed in.
- **Light / dark / system theme**, EB Garamond throughout, JetBrains Mono for labels/data.
- **LLM-optional** — set `OPENAI_API_KEY` and the backend automatically switches from the offline heuristic/synonym-bank fallback to real LLM-generated rewrites and scoring. Works fully without a key.

---

## 🏗️ Architecture

```
verbahumanize/
├── backend/
│   ├── server.py          # FastAPI app — all routes, auth, LLM + fallback logic
│   ├── requirements.txt
│   └── .env                # MONGO_URL, DB_NAME, JWT_SECRET, OPENAI_API_KEY (not committed)
└── frontend/
    ├── src/
    │   ├── pages/Home.jsx
    │   ├── components/      # RephraseWorkspace, SandboxMode, Sidebar, Navbar, modals, ui/*
    │   ├── contexts/        # AuthContext, ThemeContext
    │   └── lib/api.js       # axios instance
    ├── package.json
    └── .env                 # REACT_APP_BACKEND_URL (not committed)
```

**Backend routes**

| Method | Route                          | Notes                                                               |
|--------|---------------------------------|----------------------------------------------------------------------|
| POST   | `/api/auth/register`            | bcrypt hash, sets httpOnly JWT cookie                                |
| POST   | `/api/auth/login`               |                                                                      |
| POST   | `/api/auth/logout`              |                                                                      |
| GET    | `/api/auth/me`                  | requires cookie or `Authorization: Bearer`                          |
| POST   | `/api/analyze/pos`              | heuristic POS tagging                                                |
| POST   | `/api/rephrase`                 | LLM if `OPENAI_API_KEY` set, else synonym-bank fallback; guests capped at 350 words |
| POST   | `/api/rephrase/alternatives`    | word-level alternatives, used by both the swap modal and the Sandbox |
| POST   | `/api/detect`                   | AI/plagiarism scoring — requires sign-in                             |

**Data store:** MongoDB (via Motor, async driver). Only collection in active use today is `users`.

---

## 🖥️ Tech stack

| Layer        | Tech |
|--------------|------|
| Backend      | FastAPI, Motor (async MongoDB), PyJWT, bcrypt, Pydantic v2 |
| Frontend     | React 19, React Router, Tailwind CSS, shadcn/ui (Radix primitives), Sonner (toasts), lucide-react |
| Auth         | Email/password, JWT in an httpOnly cookie (+ bearer token fallback for the SPA) |
| Optional AI  | OpenAI (via `OPENAI_API_KEY`) — everything works without it via deterministic fallbacks |

---

## 🚀 Getting started locally (Windows / VS Code / CMD)

These steps assume **Command Prompt (`cmd.exe`)** inside VS Code's integrated terminal — not PowerShell or Git Bash. Swap the venv-activation line if you use a different shell.

### 0. Prerequisites

- [Node.js 18+](https://nodejs.org/) and Yarn (`npm install -g yarn`)
- [Python 3.11+](https://www.python.org/downloads/) added to PATH
- [MongoDB Community Server](https://www.mongodb.com/try/download/community) running on `localhost:27017` (or a free [MongoDB Atlas](https://www.mongodb.com/atlas) connection string)
- Git

### 1. Clone the repo

```cmd
git clone https://github.com/<your-username>/verbahumanize.git
cd verbahumanize
```

### 2. Backend setup

```cmd
cd backend
python -m venv venv
venv\Scripts\activate.bat
pip install -r requirements.txt
```

Create `backend\.env`:

```
MONGO_URL=mongodb://localhost:27017
DB_NAME=verbahumanize
CORS_ORIGINS=http://localhost:3000
JWT_SECRET=replace-with-a-long-random-string
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
```

> Leave `OPENAI_API_KEY` blank to run entirely on the offline fallback — no external API calls, no cost.

Run the API:

```cmd
uvicorn server:app --reload --port 8000
```

Confirm it's up by visiting `http://localhost:8000/api/` — you should see `{"message": "VerbaHumanize API", "llm": false}`.

### 3. Frontend setup

Open a **second** CMD terminal in VS Code (split the terminal panel):

```cmd
cd frontend
yarn install
```

Create `frontend\.env`:

```
REACT_APP_BACKEND_URL=http://localhost:8000
WDS_SOCKET_PORT=0
```

Run it:

```cmd
yarn start
```

This opens `http://localhost:3000`, talking to the backend on port 8000.

### 4. Verify it works

- Click **Sample** in the input pane → the parts-of-speech sidebar populates.
- Click **Rephrase** → a highlighted output appears; click any highlighted word to swap it.
- Click **Fan mode** in the Rephrase Studio header → the Word Sandbox opens below; hover a word tile to watch it cycle through alternatives. Click **Fan mode** again to close it.
- Register an account → **Check AI Level** / **Check Plagiarism** become usable.

---

## 🧪 Testing

- `test_reports/iteration_1.json` is a manual smoke-test log covering the core backend endpoints and frontend flows — useful as a regression checklist, not a CI-runnable suite.
- There is currently no automated test suite (pytest for the backend; RTL/Jest or Playwright for the frontend). See `CODE_REVIEW.md` for recommendations and a list of known issues found during review.

---

## 📌 Known limitations

- Plagiarism detection is heuristic/LLM-based, not matched against a real source corpus.
- AI detection is a heuristic/LLM approximation, not a production-grade classifier.
- See `CODE_REVIEW.md` for security/config follow-ups (CORS, secret handling, auth-token storage).

---
