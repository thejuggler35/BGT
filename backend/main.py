import hmac
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.compliance import check_content
from backend.database import connection, get_brand_rules, initialize_database, save_brand_rules
from backend.document_parser import MAX_UPLOAD_BYTES, extract_text
from backend.schemas import BrandRules, ReviewUpdate


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
    protected_paths = {"/api/health", "/api/auth/config", "/api/auth/session"}
    expected_token = os.environ.get("BGT_API_TOKEN", "")
    if (
        expected_token
        and request.method != "OPTIONS"
        and request.url.path.startswith("/api/")
        and request.url.path not in protected_paths
    ):
        auth_header = request.headers.get("authorization", "")
        scheme, _, supplied_token = auth_header.partition(" ")
        if scheme.lower() != "bearer" or not hmac.compare_digest(supplied_token, expected_token):
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
    allow_methods=["GET", "POST", "PUT", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)


def _serialize_finding(row):
    return dict(row)


def _serialize_review(conn, row):
    review = dict(row)
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
    return {"required": bool(os.environ.get("BGT_API_TOKEN"))}


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


@app.get("/api/brand-rules")
def read_brand_rules():
    with connection() as conn:
        return get_brand_rules(conn)


@app.put("/api/brand-rules")
def update_brand_rules(rules: BrandRules):
    with connection() as conn:
        save_brand_rules(conn, rules)
        return get_brand_rules(conn)


@app.post("/api/reviews")
async def create_review(
    text: str = Form(default=""),
    title: str = Form(default=""),
    file: UploadFile | None = File(default=None),
):
    source_type = "text"
    source_name = "Pasted text"
    content = text.strip()
    if file is not None and file.filename:
        safe_name = Path(file.filename.replace("\\", "/")).name
        raw = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(raw) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File is larger than the 10 MB upload limit.")
        try:
            content, source_type = extract_text(safe_name, raw)
        except ValueError as exc:
            raise HTTPException(status_code=415, detail=str(exc)) from exc
        source_name = safe_name[:255]
    if len(title) > 160:
        raise HTTPException(status_code=422, detail="Review title must be 160 characters or fewer.")
    if not content:
        raise HTTPException(status_code=422, detail="Add some draft text or upload a PDF or DOCX to review.")
    if len(content) > 200_000:
        raise HTTPException(status_code=413, detail="The extracted draft is too long. Limit content to 200,000 characters.")

    with connection() as conn:
        rules = get_brand_rules(conn)
        cursor = conn.execute(
            """
            INSERT INTO reviews (title, source_name, source_type, content)
            VALUES (?, ?, ?, ?)
            """,
            (
                title.strip()[:160] or (Path(source_name).stem if source_type != "text" else "Untitled review"),
                source_name,
                source_type,
                content,
            ),
        )
        review_id = cursor.lastrowid
        findings = check_content(content, rules)
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
def update_review(review_id: int, update: ReviewUpdate):
    if update.status is None and not update.findings and update.decision_note is None:
        raise HTTPException(status_code=422, detail="Provide a review decision or at least one finding update.")
    with connection() as conn:
        review = conn.execute("SELECT * FROM reviews WHERE id = ?", (review_id,)).fetchone()
        if review is None:
            raise HTTPException(status_code=404, detail="Review not found.")
        if update.status is not None:
            conn.execute(
                """
                UPDATE reviews
                SET status = ?, decision_note = ?, decided_at = ?
                WHERE id = ?
                """,
                (
                    update.status,
                    update.decision_note or "",
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    review_id,
                ),
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
