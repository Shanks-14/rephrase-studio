# VerbaHumanize — PRD

## Problem statement
Grammarly + Humanize-AI hybrid tool. A big curved-edges square block in the centre with:
- Header (right): rephrase-mode dropdown (synonym / antonym / rhyme / syllable-flip / academic / conversational)
- Body: split-pane input (left) vs highlighted output (right)
- Footer: input vs output word count (left) + Check AI + Check Plagiarism buttons (right)
Left sidebar: POS breakdown (nouns/verbs/adjectives/adverbs/prepositions) + dual circular scorecards (plagiarism + AI).
Click any highlighted word to open a centred modal with alternatives to swap.
Dark + light + system theme. Font: EB Garamond everywhere.

## User personas
- Students / researchers de-plagiarizing paragraphs
- Content writers dodging AI detectors
- Non-native speakers polishing tone

## Core requirements
- Rephrase modes: synonym, antonym, rhyme, syllable-flip, academic, conversational
- Word-level highlighted swaps with modal alternatives + custom input
- POS breakdown live on input
- AI + plagiarism scoring gated behind login
- Guest ≤ 350 words; logged-in unlimited
- Custom email/password auth (JWT + httpOnly cookie)

## Architecture (Python-first)
- Backend: FastAPI (all business logic in Python)
  - `/api/analyze/pos` — heuristic POS
  - `/api/rephrase` — LLM (OpenAI) if `OPENAI_API_KEY` set, else Python synonym-bank fallback
  - `/api/rephrase/alternatives` — LLM or fallback
  - `/api/detect` — LLM analysis or heuristic scoring
  - `/api/auth/*` — register/login/me/logout with bcrypt + PyJWT
- Frontend: React shell (thin) — routes, forms, theming, click handlers only

## Implemented (2026-02)
- Full centre curved-edge workspace with mode dropdown, split panes, footer stats & action buttons
- Click-to-swap highlighted output → modal with alternatives + custom input + revert
- POS sidebar with colour-coded badges
- Dual circular SVG scorecards (Plagiarism %, AI %)
- Auth modal (login + register tabs), avatar + logout popover
- Theme toggle (light / dark / system) with EB Garamond throughout
- Guest 350-word cap enforced server-side
- Backend fallback works without any API key

## Backlog
- P0: Wire real `OPENAI_API_KEY` (user promised to add) → automatically switches to real LLM
- P1: History drawer (currently stateless per user choice)
- P1: Export to DOCX / PDF
- P2: Real plagiarism source-matching (currently heuristic)
- P2: Streaming rephrase for long docs