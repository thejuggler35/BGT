# BGT

BGT (Brand Governance Technology) is a local-first review assistant for checking draft copy against a team's own approved brand guidelines. It is built for Team Optimus Prime's hackathon MVP and follows the project brief in `readme.md` and `BGT_Hackathon_Round1_Improved.pdf`.

The interface is a responsive, vanilla HTML/CSS/JavaScript app. A FastAPI REST API and SQLite database persist brand rules, product facts, review findings, and human decisions.

## Features

- Overview metrics and recent activity derived from the SQLite database, with a genuine empty state.
- Editable brand profile, restricted phrases, preferred language, and verified product facts.
- Draft review by pasted text or PDF/DOCX upload (10 MB maximum).
- Deterministic case-insensitive restricted phrase checks, contextual numeric fact comparisons, optional preferred-language suggestions, and an explicitly heuristic all-caps tone prompt.
- Evidence and guidelines attached to findings, editable/copyable suggestions, and per-finding dismiss/resolve actions.
- Human approval or change-request decision saved with an optional note. Reviews are never automatically approved.
- Searchable review history and reopenable review reports.
- Responsive layouts, keyboard-operable controls, visible loading/errors, and reduced-motion support.

## Run locally

Python 3.10 or later is recommended.

```powershell
cd G:\BGT
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
python -m uvicorn backend.main:app --reload
```

Open <http://127.0.0.1:8000>. The API health check is at <http://127.0.0.1:8000/api/health>.

The database is created as `bgt.sqlite3` in the project root on first run. Set `BGT_DATABASE_PATH` to use a different SQLite file. The first run seeds the fictional AURA Beverages workspace; later runs preserve saved rules and reviews.

The frontend loads DM Sans and Manrope from Google Fonts. The app itself and API run locally; without an internet connection, the external fonts may not load.

## Deploy

### Render (persistent SQLite)

The included [`render.yaml`](./render.yaml) creates a single-instance web service and a persistent 1 GB disk for SQLite. In Render, create a **Blueprint** from this repository and review the generated `BGT_API_TOKEN` secret before deploying. The token is required to sign in to a deployed workspace; share it only with trusted reviewers over HTTPS. The first run seeds the demo rules once, and the mounted disk keeps reviews across redeploys.

SQLite is designed here for one application instance. Do not increase the replica count or attach multiple app instances to this database; use a shared database such as PostgreSQL before scaling horizontally. Keep the persistent disk and back up `/var/data/bgt.sqlite3` before destructive infrastructure changes.

### Docker

```powershell
docker build -t bgt .
docker run --name bgt -p 8000:8000 `
  -e BGT_API_TOKEN="replace-with-a-long-random-secret" `
  -v bgt-data:/data bgt
```

Open <http://localhost:8000>. Mount `/data` on a persistent volume: the container filesystem is not a database backup. Set `BGT_DATABASE_PATH` to a writable mounted path if you use a different mount. The container runs as a non-root user and reads the platform-provided `PORT`.

For other hosting providers, run `python -m uvicorn backend.main:app --host 0.0.0.0 --port $PORT`, set a persistent `BGT_DATABASE_PATH`, and configure a strong random `BGT_API_TOKEN`. Deploy one instance and enable HTTPS.

## Demo workflow

1. Open **Brand guidelines** and edit or add a term/fact, then save.
2. Select **New review**. Paste text or upload a text-based PDF/DOCX.
3. Inspect each finding's excerpt, evidence, and related guideline. Edit or copy a suggestion, resolve or accept a finding, or dismiss it.
4. Record **Approve review** or **Request changes**. The reviewer decision and findings remain available under **Review history**.

The seeded demo includes the AURA product facts and restricted/preferred language.

## API

- `GET /api/health`
- `GET /api/brand-rules`, `PUT /api/brand-rules`
- `POST /api/reviews` (multipart form: `text`, `title`, or `file`)
- `GET /api/reviews`, `GET /api/reviews/{id}`
- `PATCH /api/reviews/{id}` (review decision/note and finding state/suggestion updates)

Interactive API documentation is available at `/docs`.

## Privacy and limitations

- Uploaded document bytes are processed in memory and are not saved; extracted review text is persisted in the local database.
- Scanned/image-only PDFs, image/logo recognition, slide decks, role-based access, multi-stage approvals, analytics, publishing integrations, and LLM review are outside this MVP.
- Numeric checks compare quantities in a sentence that names the product and a term from the fact description. They do not infer product context or validate legal meaning.
- Tone review is a basic, transparent all-caps heuristic; it is not an AI or linguistic assessment.
- This single-workspace prototype has no individual accounts, roles, or production identity provider. Treat the shared-token gate as a basic private-demo safeguard, not a substitute for an organization’s identity provider or sensitive-data controls.
- When `BGT_API_TOKEN` is configured, API access requires a bearer token; the browser keeps it in tab-scoped session storage. This is a shared-workspace access gate, not individual accounts, roles, or a full identity provider. Use HTTPS and rotate the secret if it is exposed.

## Design references

The visual and interaction direction was informed by the public principles and READMEs of [Agent Skills](https://github.com/vercel-labs/agent-skills), [Impeccable](https://github.com/pbakaus/impeccable), [Taste Skill](https://github.com/leonxlnx/taste-skill), [UI/UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill), and [Anthropic Skills](https://github.com/anthropics/skills): clear design intent, deliberate hierarchy, restrained motion, usable empty states, accessible interaction, and honest implementation boundaries. The application uses its own original interface and code.
