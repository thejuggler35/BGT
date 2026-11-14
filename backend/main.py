import base64
import hashlib
import hmac
import os
import secrets
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.compliance import check_content
from backend.database import (
    connection,
    get_brand_rules,
    get_logo_reference,
    initialize_database,
    save_brand_rules,
)
from backend.document_parser import MAX_UPLOAD_BYTES, extract_text
from backend.schemas import (
    AccountCredentials,
    AccountSetup,
    BrandRules,
    ReviewUpdate,
    TeamMemberCreate,
    TeamMemberUpdate,
)
from backend.visual import analyze_visual_image, decode_image, extract_visual_images

PASSWORD_ITERATIONS = 310_000
SESSION_DAYS = 7
PUBLIC_AUTH_PATHS = {
    "/api/health",
    "/api/auth/config",
    "/api/auth/login",
    "/api/auth/setup",
    "/api/auth/session",
}


@asynccontextmanager
async def lifespan(_app):
    access_token = os.environ.get("BGT_API_TOKEN", "")
    if access_token and len(access_token) < 32:
        raise RuntimeError("BGT_API_TOKEN must contain at least 32 characters.")
    initialize_database()
    yield


app = FastAPI(title="BGT", version="1.0.0", lifespan=lifespan)
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
MAX_REQUEST_BYTES = MAX_UPLOAD_BYTES + 1024 * 1024
cors_origins = [
    origin.strip().rstrip("/")
    for origin in os.environ.get("BGT_CORS_ORIGINS", "").split(",")
    if origin.strip()
]


@app.middleware("http")
async def protect_api_and_set_headers(request: Request, call_next):
    expected_token = os.environ.get("BGT_API_TOKEN", "")
    response = None
    if request.method != "OPTIONS" and request.url.path.startswith("/api/") and request.url.path not in PUBLIC_AUTH_PATHS:
        with connection() as conn:
            has_accounts = conn.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None
        auth_header = request.headers.get("authorization", "")
        scheme, _, supplied_token = auth_header.partition(" ")
        actor = None
        if scheme.lower() == "bearer" and supplied_token:
            if expected_token and hmac.compare_digest(supplied_token, expected_token):
                actor = {"id": None, "name": "Workspace administrator", "email": "", "role": "admin"}
            else:
                token_hash = hashlib.sha256(supplied_token.encode()).hexdigest()
                with connection() as conn:
                    row = conn.execute(
                        """
                        SELECT users.id, users.name, users.email, users.role
                        FROM user_sessions
                        JOIN users ON users.id = user_sessions.user_id
                        WHERE user_sessions.token_hash = ? AND user_sessions.expires_at > ?
                            AND users.is_active = 1
                        """,
                        (token_hash, datetime.now(timezone.utc).isoformat(timespec="seconds")),
                    ).fetchone()
                if row is not None:
                    actor = dict(row)
        if actor is not None:
            request.state.actor = actor
        elif has_accounts or expected_token:
            response = JSONResponse(status_code=401, content={"detail": "Sign in to access this workspace."})
        else:
            response = None
    else:
        response = None
    if response is None and request.url.path == "/api/reviews" and request.method == "POST":
        content_length = request.headers.get("content-length")
        if content_length and content_length.isdigit() and int(content_length) > MAX_REQUEST_BYTES:
            response = JSONResponse(status_code=413, content={"detail": "Request is larger than the 11 MB upload limit."})
    if response is None:
        response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.path in {"/docs", "/redoc", "/docs/oauth2-redirect"}:
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
            "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
            "font-src 'self' https://cdn.jsdelivr.net data:; connect-src 'self'; "
            "img-src 'self' data: https://fastapi.tiangolo.com; object-src 'none'; "
            "base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        )
    else:
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; connect-src 'self'; "
            "img-src 'self' data:; object-src 'none'; base-uri 'self'; "
            "frame-ancestors 'none'; form-action 'self'"
        )
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


def require_role(actor, *roles):
    if actor["role"] not in roles:
        raise HTTPException(status_code=403, detail="Your account does not have permission to do that.")


def current_actor(request: Request):
    actor = getattr(request.state, "actor", None)
    if actor is not None:
        return actor
    with connection() as conn:
        has_accounts = conn.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None
    if has_accounts or os.environ.get("BGT_API_TOKEN"):
        raise HTTPException(status_code=401, detail="Sign in to access this workspace.")
    return {"id": None, "name": "Local workspace", "email": "", "role": "admin"}


def hash_password(password):
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${derived.hex()}"


def verify_password(password, encoded):
    try:
        algorithm, iterations, salt, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        derived = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(derived.hex(), expected)
    except (ValueError, TypeError):
        return False


def create_session(conn, user):
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)).isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO user_sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (hashlib.sha256(token.encode()).hexdigest(), user["id"], expires_at),
    )
    return {"token": token, "expires_at": expires_at, "user": dict(user)}


def serialize_team_member(row):
    member = dict(row)
    member["is_active"] = bool(member["is_active"])
    return member


def _serialize_finding(row):
    return dict(row)


def _serialize_review(conn, row):
    review = dict(row)
    if review.get("visual_type"):
        review["source_type"] = review["visual_type"]
    if review.get("created_by") is not None:
        creator = conn.execute("SELECT name FROM users WHERE id = ?", (review["created_by"],)).fetchone()
        review["created_by_name"] = creator["name"] if creator else "Former team member"
    else:
        review["created_by_name"] = "Workspace"
    if review.get("decided_by") is not None:
        decider = conn.execute("SELECT name FROM users WHERE id = ?", (review["decided_by"],)).fetchone()
        review["decided_by_name"] = decider["name"] if decider else "Former team member"
    else:
        review["decided_by_name"] = None
    if review.get("assigned_to") is not None:
        assignee = conn.execute(
            "SELECT name FROM users WHERE id = ? AND is_active = 1", (review["assigned_to"],)
        ).fetchone()
        review["assigned_to_name"] = assignee["name"] if assignee else "Inactive team member"
    else:
        review["assigned_to_name"] = None
    events = conn.execute(
        """
        SELECT decision_events.status, decision_events.note, decision_events.decided_at,
               users.name AS decided_by_name
        FROM decision_events
        LEFT JOIN users ON users.id = decision_events.user_id
        WHERE decision_events.review_id = ? ORDER BY decision_events.id
        """,
        (review["id"],),
    ).fetchall()
    review["decision_history"] = [
        {**dict(event), "decided_by_name": event["decided_by_name"] or "Workspace"}
        for event in events
    ]
    finding_rows = conn.execute(
        "SELECT * FROM findings WHERE review_id = ? ORDER BY id", (review["id"],)
    ).fetchall()
    review["findings"] = [_serialize_finding(finding) for finding in finding_rows]
    review["finding_count"] = len(finding_rows)
    review["open_count"] = sum(finding["state"] == "open" for finding in finding_rows)
    return review


@app.get("/")
def home():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/health")
def health():
    with connection() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok"}


@app.get("/api/auth/config")
def auth_config():
    with connection() as conn:
        accounts_enabled = conn.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None
    return {
        "required": bool(os.environ.get("BGT_API_TOKEN")),
        "accounts_enabled": accounts_enabled,
        "setup_required": not accounts_enabled,
        "bootstrap_requires_token": bool(os.environ.get("BGT_API_TOKEN")),
    }


@app.post("/api/auth/setup")
def setup_first_account(setup: AccountSetup):
    expected_token = os.environ.get("BGT_API_TOKEN", "")
    if expected_token and not hmac.compare_digest(setup.workspace_token, expected_token):
        raise HTTPException(status_code=401, detail="The workspace access token is not correct.")
    with connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None:
            raise HTTPException(status_code=409, detail="The first administrator account has already been created.")
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, 'admin')",
            (setup.name, setup.email, hash_password(setup.password)),
        )
        user = conn.execute(
            "SELECT id, name, email, role FROM users WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return create_session(conn, user)


@app.post("/api/auth/login")
def login(credentials: AccountCredentials):
    with connection() as conn:
        user = conn.execute(
            "SELECT id, name, email, password_hash, role, is_active FROM users WHERE email = ?",
            (credentials.email,),
        ).fetchone()
        valid = user is not None and user["is_active"] and verify_password(credentials.password, user["password_hash"])
        if not valid:
            hashlib.pbkdf2_hmac(
                "sha256", credentials.password.encode(), b"bgt-login-no-user", PASSWORD_ITERATIONS
            )
            raise HTTPException(status_code=401, detail="Email or password is not correct.")
        conn.execute("DELETE FROM user_sessions WHERE expires_at <= ?", (datetime.now(timezone.utc).isoformat(),))
        return create_session(conn, {key: user[key] for key in ("id", "name", "email", "role")})


@app.get("/api/auth/me")
def read_current_user(actor=Depends(current_actor)):
    return actor


@app.post("/api/auth/session")
def create_auth_session(authorization: str | None = Header(default=None)):
    expected_token = os.environ.get("BGT_API_TOKEN", "")
    scheme, _, supplied_token = (authorization or "").partition(" ")
    if expected_token and (
        scheme.lower() != "bearer" or not hmac.compare_digest(supplied_token, expected_token)
    ):
        raise HTTPException(status_code=401, detail="That access token is not correct.")
    if not expected_token:
        raise HTTPException(status_code=409, detail="Workspace access protection is not enabled.")
    return {"authenticated": True}


@app.delete("/api/auth/session")
def revoke_current_session(request: Request):
    auth_header = request.headers.get("authorization", "")
    _, _, token = auth_header.partition(" ")
    if token and not hmac.compare_digest(token, os.environ.get("BGT_API_TOKEN", "")):
        with connection() as conn:
            conn.execute("DELETE FROM user_sessions WHERE token_hash = ?", (hashlib.sha256(token.encode()).hexdigest(),))
    return {"authenticated": False}


@app.get("/api/team")
def list_team(actor=Depends(current_actor)):
    require_role(actor, "admin")
    with connection() as conn:
        rows = conn.execute(
            "SELECT id, name, email, role, is_active, created_at FROM users ORDER BY name COLLATE NOCASE"
        ).fetchall()
        return [serialize_team_member(row) for row in rows]


@app.get("/api/team/reviewers")
def list_reviewers(actor=Depends(current_actor)):
    require_role(actor, "admin", "creator")
    with connection() as conn:
        rows = conn.execute(
            "SELECT id, name FROM users WHERE role = 'reviewer' AND is_active = 1 ORDER BY name COLLATE NOCASE"
        ).fetchall()
        return [dict(row) for row in rows]


@app.post("/api/team", status_code=201)
def add_team_member(member: TeamMemberCreate, actor=Depends(current_actor)):
    require_role(actor, "admin")
    with connection() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                (member.name, member.email, hash_password(member.password), member.role),
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=409, detail="An account with that email already exists.") from exc
        row = conn.execute(
            "SELECT id, name, email, role, is_active, created_at FROM users WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        return serialize_team_member(row)


@app.patch("/api/team/{user_id}")
def update_team_member(user_id: int, update: TeamMemberUpdate, actor=Depends(current_actor)):
    require_role(actor, "admin")
    if update.role is None and update.is_active is None:
        raise HTTPException(status_code=422, detail="Provide a role or account status change.")
    with connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            raise HTTPException(status_code=404, detail="Team member not found.")
        new_role = update.role or user["role"]
        new_active = user["is_active"] if update.is_active is None else int(update.is_active)
        if user_id == actor["id"] and not new_active:
            raise HTTPException(status_code=409, detail="You cannot deactivate your own account.")
        if user["role"] == "admin" and user["is_active"] and (new_role != "admin" or not new_active):
            admins = conn.execute(
                "SELECT COUNT(*) AS count FROM users WHERE role = 'admin' AND is_active = 1"
            ).fetchone()["count"]
            if admins <= 1:
                raise HTTPException(status_code=409, detail="The workspace must keep at least one active administrator.")
        conn.execute("UPDATE users SET role = ?, is_active = ? WHERE id = ?", (new_role, new_active, user_id))
        row = conn.execute(
            "SELECT id, name, email, role, is_active, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return serialize_team_member(row)


@app.get("/api/brand-rules")
def read_brand_rules():
    with connection() as conn:
        return get_brand_rules(conn)


@app.put("/api/brand-rules")
def update_brand_rules(rules: BrandRules, actor=Depends(current_actor)):
    require_role(actor, "admin", "creator")
    if rules.logo_reference_data:
        header, encoded = rules.logo_reference_data.split(",", 1)
        expected_format = {"image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WEBP"}[
            header[5:].split(";", 1)[0]
        ]
        try:
            reference = decode_image(
                base64.b64decode(encoded, validate=True),
                expected_format=expected_format,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"Invalid logo reference: {exc}") from exc
        if min(reference.size) < 8:
            raise HTTPException(status_code=422, detail="Logo reference must be at least 8 pixels wide and tall.")
    with connection() as conn:
        save_brand_rules(conn, rules)
        return get_brand_rules(conn)


@app.post("/api/reviews")
async def create_review(
    text: str = Form(default=""),
    title: str = Form(default=""),
    file: UploadFile | None = File(default=None),
    actor=Depends(current_actor),
):
    require_role(actor, "admin", "creator")
    source_type = "text"
    visual_type = ""
    source_name = "Pasted text"
    content = text.strip()
    visual_images = []
    visual_truncated = False
    if file is not None and file.filename:
        safe_name = Path(file.filename.replace("\\", "/")).name
        raw = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(raw) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File is larger than the 10 MB upload limit.")
        suffix = Path(safe_name).suffix.lower()
        try:
            if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
                visual_images, visual_truncated = extract_visual_images(safe_name, raw)
                visual_type = "image"
            else:
                content, source_type = extract_text(safe_name, raw, allow_empty=True)
                visual_images, visual_truncated = extract_visual_images(safe_name, raw)
        except ValueError as exc:
            raise HTTPException(status_code=415, detail=str(exc)) from exc
        source_name = safe_name[:255]
    if len(title) > 160:
        raise HTTPException(status_code=422, detail="Review title must be 160 characters or fewer.")
    if not content and not visual_images:
        raise HTTPException(status_code=422, detail="Add draft text or upload a readable PDF, DOCX, PNG, JPEG, or WebP file.")
    if len(content) > 200_000:
        raise HTTPException(status_code=413, detail="The extracted draft is too long. Limit content to 200,000 characters.")

    with connection() as conn:
        rules = get_brand_rules(conn)
        cursor = conn.execute(
            """
            INSERT INTO reviews (title, source_name, source_type, content, created_by, visual_type)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                title.strip()[:160] or (
                    Path(source_name).stem if source_type != "text" or visual_type else "Untitled review"
                ),
                source_name,
                source_type,
                content,
                actor["id"],
                visual_type,
            ),
        )
        review_id = cursor.lastrowid
        findings = check_content(content, rules) if content else []
        if visual_images:
            visual = get_logo_reference(conn)
            logo_reference = visual["logo_reference"]
            palette = rules["visual_palette"]
            for image, location in visual_images:
                for finding in analyze_visual_image(image, palette, logo_reference):
                    finding["evidence"] = f"{location}: {finding['evidence']}".rstrip()
                    findings.append(finding)
            if visual_truncated:
                findings.append({
                    "category": "visual_guidance",
                    "title": "Visual review was limited",
                    "severity": "info",
                    "matched_text": "",
                    "explanation": "The file contained more pages or images than the visual review limit, so only the first 20 were checked.",
                    "evidence": "Visual processing limit: 20 pages or embedded images.",
                    "guideline": "",
                    "suggestion": "",
                })
        conn.executemany(
            """
            INSERT INTO findings
                (review_id, category, title, severity, matched_text, explanation, evidence, guideline, suggestion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    review_id,
                    item["category"],
                    item["title"],
                    item["severity"],
                    item["matched_text"],
                    item["explanation"],
                    item["evidence"],
                    item["guideline"],
                    item["suggestion"],
                )
                for item in findings
            ],
        )
        row = conn.execute("SELECT * FROM reviews WHERE id = ?", (review_id,)).fetchone()
        return _serialize_review(conn, row)


@app.get("/api/reviews")
def list_reviews():
    with connection() as conn:
        rows = conn.execute("SELECT * FROM reviews ORDER BY created_at DESC, id DESC").fetchall()
        return [_serialize_review(conn, row) for row in rows]


@app.get("/api/reviews/{review_id}")
def get_review(review_id: int):
    with connection() as conn:
        row = conn.execute("SELECT * FROM reviews WHERE id = ?", (review_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Review not found.")
        return _serialize_review(conn, row)


@app.patch("/api/reviews/{review_id}")
def update_review(review_id: int, update: ReviewUpdate, actor=Depends(current_actor)):
    has_assignment = "assigned_to" in update.model_fields_set
    has_review_updates = update.status is not None or bool(update.findings) or update.decision_note is not None
    if not has_assignment and not has_review_updates:
        raise HTTPException(status_code=422, detail="Provide a review decision or at least one finding update.")
    if has_assignment:
        require_role(actor, "admin", "creator")
    if has_review_updates:
        require_role(actor, "admin", "reviewer")
    with connection() as conn:
        review = conn.execute("SELECT * FROM reviews WHERE id = ?", (review_id,)).fetchone()
        if review is None:
            raise HTTPException(status_code=404, detail="Review not found.")
        if has_review_updates and actor["role"] == "reviewer" and review["assigned_to"] != actor["id"]:
            raise HTTPException(status_code=403, detail="This review is not assigned to your account.")
        if has_assignment and update.assigned_to is not None:
            assignee = conn.execute(
                "SELECT id FROM users WHERE id = ? AND role = 'reviewer' AND is_active = 1",
                (update.assigned_to,),
            ).fetchone()
            if assignee is None:
                raise HTTPException(status_code=422, detail="Assign the review to an active reviewer.")
            conn.execute("UPDATE reviews SET assigned_to = ? WHERE id = ?", (update.assigned_to, review_id))
        if update.status is not None:
            decided_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            conn.execute(
                """
                UPDATE reviews
                SET status = ?, decision_note = ?, decided_at = ?, decided_by = ?
                WHERE id = ?
                """,
                (
                    update.status,
                    update.decision_note or "",
                    decided_at,
                    actor["id"],
                    review_id,
                ),
            )
            conn.execute(
                """
                INSERT INTO decision_events (review_id, user_id, status, note, decided_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (review_id, actor["id"], update.status, update.decision_note or "", decided_at),
            )
        elif update.decision_note is not None:
            conn.execute(
                "UPDATE reviews SET decision_note = ? WHERE id = ?",
                (update.decision_note, review_id),
            )
        for finding in update.findings:
            if finding.state is None and finding.suggestion is None:
                continue
            changes = []
            params = []
            if finding.state is not None:
                changes.append("state = ?")
                params.append(finding.state)
            if finding.suggestion is not None:
                changes.append("suggestion = ?")
                params.append(finding.suggestion)
                if finding.state is None:
                    changes.append("state = 'edited'")
            params.extend([finding.id, review_id])
            cursor = conn.execute(
                f"UPDATE findings SET {', '.join(changes)} WHERE id = ? AND review_id = ?",
                params,
            )
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail=f"Finding {finding.id} was not found in this review.")
        row = conn.execute("SELECT * FROM reviews WHERE id = ?", (review_id,)).fetchone()
        return _serialize_review(conn, row)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
