# BGT

BGT (Brand Governance Technology) helps a team check draft marketing content against its saved brand guidelines and product facts. It highlights wording and claims for a person to review; it does not make approval decisions or publish content.

## What BGT does

- Stores a brand profile, voice and tone guidance, restricted phrases, preferred wording, and numeric product facts.
- Checks pasted drafts or text-based PDF and DOCX files against those saved rules.
- Shows the matched text, relevant guideline, evidence, and a suggested edit for each finding.
- Saves reviews and reviewer decisions so they can be searched and reopened later.
- Lets reviewers edit suggestions, resolve or dismiss findings, and approve a review or request changes.

The checks are rule-based. Restricted phrases are matched without regard to case. Product quantities are compared when the sentence contains the product name and a relevant fact term. Missing preferred wording produces a suggestion. The tone prompt is a simple all-caps heuristic. Findings are prompts for human review, not confirmed violations.

## Run locally

Python 3.10 or later is recommended.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
python -m uvicorn backend.main:app --reload
```

Open <http://127.0.0.1:8000>. Interactive API documentation is available at <http://127.0.0.1:8000/docs>, and the health check is at <http://127.0.0.1:8000/api/health>.

On first run, BGT creates `bgt.sqlite3` in the repository root and seeds an example AURA Beverages workspace. Saved guidelines and reviews are stored in SQLite. Set `BGT_DATABASE_PATH` to use a different database file.

## Website and backend

The public website is <https://thejuggler35.github.io/BGT/>. GitHub Pages hosts the static frontend; it does not run the Python API. The live FastAPI backend runs separately on Railway, with its SQLite database stored on a persistent volume.

The Pages workflow publishes the frontend when changes are pushed to `main`. It reads the repository Actions variable `BGT_API_BASE_URL` to configure the API address. The variable should contain the backend's HTTPS origin, for example `https://your-service.up.railway.app`, without a trailing slash.

For a new Railway deployment, use the repository's root `Dockerfile`, attach a persistent volume at `/data`, and configure these service variables:

| Variable | Value |
| --- | --- |
| `BGT_DATABASE_PATH` | `/data/bgt.sqlite3` |
| `BGT_CORS_ORIGINS` | `https://thejuggler35.github.io` |
| `RAILWAY_RUN_UID` | `0` |
| `BGT_API_TOKEN` | A private random value with at least 32 characters |

Generate a token locally, for example with `python -c "import secrets; print(secrets.token_hex(32))"`. Add the result directly to Railway as `BGT_API_TOKEN`. Do not put it in GitHub, the frontend, or this file. Keep the token private and rotate it in Railway if it is exposed.

In the GitHub repository, add `BGT_API_BASE_URL` under **Settings → Secrets and variables → Actions → Variables**. This URL is public configuration, not a credential. Run **Actions → Deploy BGT to GitHub Pages** after changing the value.

When authentication is enabled, BGT asks reviewers for the shared workspace token. It is held in the browser tab's session storage. Anyone with the token can access the shared workspace; this is not an individual account or role system. Use HTTPS and keep the Railway service to one instance while it uses SQLite. Hosting costs depend on the provider's plan and usage.

## Review a draft

1. Open **Brand guidelines** to review or update the saved rules and product facts.
2. Choose **New review**, paste draft text or upload a PDF/DOCX file, then run the check.
3. Review each finding and its evidence. Edit a suggestion, or resolve or dismiss the finding as appropriate.
4. Record **Approve review** or **Request changes**. Reopen saved reviews from **Review history**.

## API

- `GET /api/health`
- `GET /api/auth/config`
- `POST /api/auth/session`
- `GET` and `PUT /api/brand-rules`
- `POST /api/reviews` for pasted text or PDF/DOCX uploads
- `GET /api/reviews` and `GET /api/reviews/{id}`
- `PATCH /api/reviews/{id}` to update findings or save a review decision

Protected API requests use the `Authorization: Bearer <token>` header when `BGT_API_TOKEN` is configured. The health and authentication setup endpoints remain available without a token.

## Limits

- PDF and DOCX uploads are limited to 10 MB. Scanned/image-only PDFs and formats other than PDF or DOCX are not supported.
- Extracted draft text is stored in the database with the review. Uploaded file bytes are processed in memory and are not retained.
- Drafts are limited to 200,000 characters.
- Numeric checks require matching product and fact context; they do not establish legal or scientific accuracy.
- BGT does not provide image or logo review, individual user accounts, role-based access, or automated content approval.
