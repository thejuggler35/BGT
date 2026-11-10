import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


DATABASE_PATH = Path(
    os.environ.get(
        "BGT_DATABASE_PATH",
        str(Path(__file__).resolve().parent.parent / "bgt.sqlite3"),
    )
)

DEMO_RULES = {
    "brand_name": "AURA Beverages",
    "brand_voice": ["Friendly", "Confident", "Clear"],
    "tone_characteristics": "Use plain language, keep claims grounded, and sound upbeat without shouting.",
    "restricted_terms": [
        {"phrase": "Guaranteed results", "explanation": "Avoid promises that imply a guaranteed outcome."},
        {"phrase": "Cure fatigue", "explanation": "Avoid medical or health-treatment claims."},
    ],
    "preferred_terms": [
        {"phrase": "Refreshing drink", "explanation": "Use this approved product description where it fits naturally."},
    ],
    "product_facts": [
        {"product": "AURA Energy", "fact": "Caffeine per serving", "value": 80, "unit": "mg"},
        {"product": "AURA Energy", "fact": "Volume per can", "value": 250, "unit": "ml"},
        {"product": "AURA Zero", "fact": "Added sugar", "value": 0, "unit": "g"},
    ],
}


@contextmanager
def connection():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_database():
    with connection() as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS brand_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                brand_name TEXT NOT NULL,
                brand_voice TEXT NOT NULL,
                tone_characteristics TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS terms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL CHECK (category IN ('restricted', 'preferred')),
                phrase TEXT NOT NULL,
                explanation TEXT NOT NULL DEFAULT '',
                UNIQUE(category, phrase)
            );
            CREATE TABLE IF NOT EXISTS product_facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product TEXT NOT NULL,
                fact TEXT NOT NULL,
                value REAL,
                unit TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                source_name TEXT NOT NULL,
                source_type TEXT NOT NULL CHECK (source_type IN ('text', 'pdf', 'docx')),
                content TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'needs_review'
                    CHECK (status IN ('needs_review', 'approved', 'changes_requested')),
                decision_note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                decided_at TEXT
            );
            CREATE TABLE IF NOT EXISTS findings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                review_id INTEGER NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                severity TEXT NOT NULL CHECK (severity IN ('attention', 'suggestion', 'info')),
                matched_text TEXT NOT NULL DEFAULT '',
                explanation TEXT NOT NULL,
                evidence TEXT NOT NULL DEFAULT '',
                guideline TEXT NOT NULL DEFAULT '',
                suggestion TEXT NOT NULL DEFAULT '',
                state TEXT NOT NULL DEFAULT 'open'
                    CHECK (state IN ('open', 'dismissed', 'resolved', 'accepted', 'edited'))
            );
            CREATE INDEX IF NOT EXISTS idx_reviews_created ON reviews(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_findings_review ON findings(review_id);
            """
        )
        if conn.execute("SELECT 1 FROM brand_settings WHERE id = 1").fetchone() is None:
            conn.execute(
                "INSERT INTO brand_settings (id, brand_name, brand_voice, tone_characteristics) VALUES (1, ?, ?, ?)",
                (
                    DEMO_RULES["brand_name"],
                    ", ".join(DEMO_RULES["brand_voice"]),
                    DEMO_RULES["tone_characteristics"],
                ),
            )
            conn.executemany(
                "INSERT INTO terms (category, phrase, explanation) VALUES (?, ?, ?)",
                [
                    ("restricted", item["phrase"], item["explanation"])
                    for item in DEMO_RULES["restricted_terms"]
                ]
                + [
                    ("preferred", item["phrase"], item["explanation"])
                    for item in DEMO_RULES["preferred_terms"]
                ],
            )
            conn.executemany(
                "INSERT INTO product_facts (product, fact, value, unit) VALUES (?, ?, ?, ?)",
                [
                    (item["product"], item["fact"], item["value"], item["unit"])
                    for item in DEMO_RULES["product_facts"]
                ],
            )


def get_brand_rules(conn):
    settings = conn.execute("SELECT * FROM brand_settings WHERE id = 1").fetchone()
    terms = conn.execute(
        "SELECT category, phrase, explanation FROM terms ORDER BY id"
    ).fetchall()
    facts = conn.execute(
        "SELECT id, product, fact, value, unit FROM product_facts ORDER BY id"
    ).fetchall()
    grouped = {"restricted": [], "preferred": []}
    for row in terms:
        grouped[row["category"]].append(
            {"phrase": row["phrase"], "explanation": row["explanation"]}
        )
    return {
        "brand_name": settings["brand_name"],
        "brand_voice": [part.strip() for part in settings["brand_voice"].split(",") if part.strip()],
        "tone_characteristics": settings["tone_characteristics"],
        "restricted_terms": grouped["restricted"],
        "preferred_terms": grouped["preferred"],
        "product_facts": [dict(row) for row in facts],
        "updated_at": settings["updated_at"],
    }


def save_brand_rules(conn, rules):
    conn.execute(
        """
        UPDATE brand_settings
        SET brand_name = ?, brand_voice = ?, tone_characteristics = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = 1
        """,
        (rules.brand_name.strip(), ", ".join(rules.brand_voice), rules.tone_characteristics.strip()),
    )
    conn.execute("DELETE FROM terms")
    conn.executemany(
        "INSERT INTO terms (category, phrase, explanation) VALUES (?, ?, ?)",
        [
            ("restricted", item.phrase.strip(), item.explanation.strip())
            for item in rules.restricted_terms
        ]
        + [
            ("preferred", item.phrase.strip(), item.explanation.strip())
            for item in rules.preferred_terms
        ],
    )
    conn.execute("DELETE FROM product_facts")
    conn.executemany(
        "INSERT INTO product_facts (product, fact, value, unit) VALUES (?, ?, ?, ?)",
        [
            (item.product.strip(), item.fact.strip(), item.value, item.unit.strip())
            for item in rules.product_facts
        ],
    )
