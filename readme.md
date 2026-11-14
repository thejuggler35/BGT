# BGT

BGT (Brand Governance Technology) helps a team check draft marketing content against its saved brand guidelines and product facts. It highlights wording and claims for a person to review; it does not make approval decisions or publish content.

## What BGT does

- Stores a brand profile, voice and tone guidance, restricted phrases, preferred wording, numeric product facts, approved colors, and an optional logo reference.
- Checks pasted drafts, PDF/DOCX documents, and PNG/JPEG/WebP images against saved text and visual guidelines.
- Shows the matched text, relevant guideline, evidence, and a suggested edit for each finding.
- Saves reviews and reviewer decisions so they can be searched and reopened later.
- Lets reviewers edit suggestions, resolve or dismiss findings, and approve a review or request changes.

The checks are rule-based. Restricted phrases are matched without regard to case. Product quantities are compared when the sentence contains the product name and a relevant fact term. Missing preferred wording produces a suggestion. Visual checks compare prominent sampled colors with the saved palette and look for a shape similar to the saved logo reference. These checks are approximate: natural imagery may include off-palette colors, and logo checks do not establish correct placement, clear space, or distortion. Findings are prompts for human review, not confirmed violations.

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

The first visit to a new database prompts you to create an administrator account. On a deployed service, configure `BGT_API_TOKEN` before setup; the first administrator must provide this token. Without it, initial setup is intentionally available to the first visitor, so do not expose an unconfigured service to the public internet. Existing databases and reviews are preserved by additive SQLite migrations.

Administrators can use **Create sign-in** on **Team members** to add accounts and assign a role, and can deactivate accounts from the same page. Accounts have individual email/password sign-in and seven-day browser-tab sessions. Passwords are stored as salted PBKDF2 hashes. Share initial passwords with teammates securely. Roles are enforced by the API:

If account sign-in is enabled, **Use workspace access token** on the sign-in screen allows a trusted administrator to enter the private `BGT_API_TOKEN` directly. **Create sign-in using token** opens an account-creation form that requires this token and lets the administrator select a role. The token grants administrator access; use it only on a trusted device. It is cleared after account creation or a failed request. Prefer individual accounts for everyday use.

| Role | Permissions |
| --- | --- |
| Administrator | Manage accounts, guidelines, reviews, findings, and decisions |
| Content creator | Edit guidelines, create reviews, and assign them to active reviewers |
| Reviewer | Update findings and record decisions on reviews assigned to them |

Review records show who created them and who recorded each decision, with decision history retained. The configured `BGT_API_TOKEN` remains a high-privilege administrator recovery credential; keep it private. Use HTTPS and keep the Railway service to one instance while it uses SQLite. Hosting costs depend on the provider's plan and usage.

## Review a draft

1. Open **Brand guidelines** to review or update the saved rules and product facts.
2. Choose **New review**, paste draft text or upload a PDF/DOCX/image file, then run the check.
3. Review each finding and its evidence. Edit a suggestion, or resolve or dismiss the finding as appropriate.
4. Record **Approve review** or **Request changes**. Reopen saved reviews from **Review history**.

## API

- `GET /api/health`
- `GET /api/auth/config`
- `POST /api/auth/setup` to create the first administrator account
- `POST /api/auth/login` and `GET /api/auth/me`
- `GET /api/team`, `POST /api/team`, and `PATCH /api/team/{id}` (administrators)
- `POST /api/auth/session`
- `GET` and `PUT /api/brand-rules`
- `POST /api/reviews` for pasted text or PDF/DOCX/PNG/JPEG/WebP uploads
- `GET /api/reviews` and `GET /api/reviews/{id}`
- `PATCH /api/reviews/{id}` to update findings or save a review decision

Protected API requests use the `Authorization: Bearer <token>` header when `BGT_API_TOKEN` is configured. The health and authentication setup endpoints remain available without a token.

## Limits

- PDF, DOCX, and image uploads are limited to 10 MB. Visual checks process at most 20 PDF pages or DOCX embedded images, limit raster images to 25 megapixels, and downsample inputs for analysis.
- Logo reference images are limited to 2 MB. Uploaded content is analyzed in memory; binary uploads are not retained with review records.
- Extracted draft text is stored in the database with the review. Uploaded file bytes are processed in memory and are not retained.
- Drafts are limited to 200,000 characters.
- Numeric checks require matching product and fact context; they do not establish legal or scientific accuracy.
- Visual checks are heuristic and can miss altered or small logos and can flag legitimate photo colors. They do not replace manual review. BGT does not provide email-based password recovery or automated content approval.
