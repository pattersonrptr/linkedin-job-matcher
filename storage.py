"""
Operações de banco de dados SQLite para o LinkedIn Job Matcher V2.
Upsert, consulta, filtros e exportação CSV.
"""

import csv
import json
import sqlite3
from pathlib import Path

from models import JobFilter, JobResult

# ── Schema principal ──
_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    company TEXT NOT NULL DEFAULT '',
    location TEXT DEFAULT '',
    country TEXT DEFAULT '',
    link TEXT DEFAULT '',
    description TEXT DEFAULT '',
    score INTEGER,
    matched_skills TEXT DEFAULT '[]',
    familiar_skills TEXT DEFAULT '[]',
    missing_skills TEXT DEFAULT '[]',
    seniority_match TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    query_source TEXT DEFAULT '',
    is_closed INTEGER DEFAULT 0,
    is_easy_apply INTEGER DEFAULT 0,
    work_type TEXT DEFAULT '',
    has_salary INTEGER DEFAULT 0,
    salary_min INTEGER,
    salary_max INTEGER,
    salary_currency TEXT DEFAULT '',
    listed_at_ts INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# Colunas adicionadas após a versão inicial — migration segura
_MIGRATION_COLUMNS: list[tuple[str, str]] = [
    ("country", "TEXT DEFAULT ''"),
    ("is_closed", "INTEGER DEFAULT 0"),
    ("is_easy_apply", "INTEGER DEFAULT 0"),
    ("work_type", "TEXT DEFAULT ''"),
    ("has_salary", "INTEGER DEFAULT 0"),
    ("salary_min", "INTEGER"),
    ("salary_max", "INTEGER"),
    ("salary_currency", "TEXT DEFAULT ''"),
    ("listed_at_ts", "INTEGER DEFAULT 0"),
    ("familiar_skills", "TEXT DEFAULT '[]'"),
]


def _migrate_db(conn: sqlite3.Connection) -> None:
    """Adiciona colunas novas a um banco existente sem recriar a tabela."""
    for col_name, col_def in _MIGRATION_COLUMNS:
        try:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {col_name} {col_def}")
        except sqlite3.OperationalError:
            pass  # Coluna já existe
    conn.commit()


def init_db(db_path: str | Path = "job_matcher.db") -> sqlite3.Connection:
    """Inicializa o banco SQLite, aplica schema e migrações, retorna conexão."""
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    conn.commit()
    _migrate_db(conn)
    return conn


def job_to_row(job: JobResult) -> dict:
    """Converte JobResult em dicionário para SQL."""
    return {
        "job_id": job.job_id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "country": job.country,
        "link": job.link,
        "description": job.description,
        "score": job.score,
        "matched_skills": json.dumps(job.matched_skills, ensure_ascii=False),
        "familiar_skills": json.dumps(job.familiar_skills, ensure_ascii=False),
        "missing_skills": json.dumps(job.missing_skills, ensure_ascii=False),
        "seniority_match": job.seniority_match,
        "summary": job.summary,
        "query_source": job.query_source,
        "is_closed": int(job.is_closed),
        "is_easy_apply": int(job.is_easy_apply),
        "work_type": job.work_type,
        "has_salary": int(job.has_salary),
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "salary_currency": job.salary_currency,
        "listed_at_ts": job.listed_at_ts,
    }


def row_to_job(row: sqlite3.Row) -> JobResult:
    """Converte sqlite3.Row de volta em JobResult."""
    def _loads(val: str | None) -> list[str]:
        if not val:
            return []
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return []

    keys = row.keys()
    return JobResult(
        job_id=str(row["job_id"]),
        title=str(row["title"]),
        company=str(row["company"]),
        location=str(row["location"] or ""),
        country=str(row["country"] if "country" in keys else "") or "",
        link=str(row["link"] or ""),
        description=str(row["description"] or ""),
        score=row["score"],
        matched_skills=_loads(row["matched_skills"]),
        familiar_skills=_loads(row["familiar_skills"] if "familiar_skills" in keys else None),
        missing_skills=_loads(row["missing_skills"]),
        seniority_match=str(row["seniority_match"] or ""),
        summary=str(row["summary"] or ""),
        query_source=str(row["query_source"] or ""),
        is_closed=bool(row["is_closed"] if "is_closed" in keys else False),
        is_easy_apply=bool(row["is_easy_apply"] if "is_easy_apply" in keys else False),
        work_type=str(row["work_type"] if "work_type" in keys else "") or "",
        has_salary=bool(row["has_salary"] if "has_salary" in keys else False),
        salary_min=row["salary_min"] if "salary_min" in keys else None,
        salary_max=row["salary_max"] if "salary_max" in keys else None,
        salary_currency=str(row["salary_currency"] if "salary_currency" in keys else "") or "",
        listed_at_ts=int(row["listed_at_ts"] if "listed_at_ts" in keys else 0) or 0,
    )


def upsert_job(conn: sqlite3.Connection, job: JobResult) -> None:
    """Insere ou atualiza um job pelo job_id (ON CONFLICT)."""
    row = job_to_row(job)
    conn.execute(
        """
        INSERT INTO jobs (
            job_id, title, company, location, country, link, description,
            score, matched_skills, familiar_skills, missing_skills, seniority_match,
            summary, query_source,
            is_closed, is_easy_apply, work_type,
            has_salary, salary_min, salary_max, salary_currency, listed_at_ts
        ) VALUES (
            :job_id, :title, :company, :location, :country, :link, :description,
            :score, :matched_skills, :familiar_skills, :missing_skills, :seniority_match,
            :summary, :query_source,
            :is_closed, :is_easy_apply, :work_type,
            :has_salary, :salary_min, :salary_max, :salary_currency, :listed_at_ts
        )
        ON CONFLICT(job_id) DO UPDATE SET
            title = excluded.title,
            company = excluded.company,
            location = excluded.location,
            country = excluded.country,
            link = excluded.link,
            description = excluded.description,
            score = excluded.score,
            matched_skills = excluded.matched_skills,
            familiar_skills = excluded.familiar_skills,
            missing_skills = excluded.missing_skills,
            seniority_match = excluded.seniority_match,
            summary = excluded.summary,
            query_source = excluded.query_source,
            is_closed = excluded.is_closed,
            is_easy_apply = excluded.is_easy_apply,
            work_type = excluded.work_type,
            has_salary = excluded.has_salary,
            salary_min = excluded.salary_min,
            salary_max = excluded.salary_max,
            salary_currency = excluded.salary_currency,
            listed_at_ts = excluded.listed_at_ts,
            updated_at = CURRENT_TIMESTAMP
        """,
        row,
    )
    conn.commit()


def get_all_jobs(conn: sqlite3.Connection) -> list[JobResult]:
    """Retorna todos os jobs do banco."""
    cursor = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC")
    return [row_to_job(r) for r in cursor.fetchall()]


def get_analyzed_job_ids(conn: sqlite3.Connection) -> set[str]:
    """Retorna set de job_ids que já foram analisados (score != NULL)."""
    cursor = conn.execute("SELECT job_id FROM jobs WHERE score IS NOT NULL")
    return {str(r["job_id"]) for r in cursor.fetchall()}


def get_collected_job_ids(conn: sqlite3.Connection) -> set[str]:
    """Retorna set de todos os job_ids coletados (com ou sem análise)."""
    cursor = conn.execute("SELECT job_id FROM jobs")
    return {str(r["job_id"]) for r in cursor.fetchall()}


def purge_old_jobs(conn: sqlite3.Connection, max_age_days: int) -> int:
    """Remove vagas com mais de max_age_days dias no banco. Retorna quantidade removida."""
    import time
    cutoff_ts = int(time.time()) - (max_age_days * 86_400)
    # Remove por listed_at_ts (data de postagem no LinkedIn) quando disponível,
    # senão por created_at (data de inserção no banco)
    cursor = conn.execute(
        """
        DELETE FROM jobs
        WHERE (listed_at_ts > 0 AND listed_at_ts < ?)
           OR (listed_at_ts = 0 AND created_at < datetime(?, 'unixepoch'))
        """,
        (cutoff_ts, cutoff_ts),
    )
    conn.commit()
    return cursor.rowcount


def get_filtered_jobs(
    conn: sqlite3.Connection,
    job_filter: JobFilter | None = None,
) -> list[JobResult]:
    """Retorna jobs de acordo com os filtros, ordenados conforme job_filter.sort."""
    import time

    f = job_filter or JobFilter()

    where_parts: list[str] = []
    params: list = []

    if f.min_score > 0:
        where_parts.append("score >= ?")
        params.append(f.min_score)

    if f.has_salary:
        where_parts.append("has_salary = 1")

    if f.min_salary is not None:
        where_parts.append("salary_min >= ?")
        params.append(f.min_salary)

    if f.currency:
        where_parts.append("salary_currency = ?")
        params.append(f.currency.upper())

    if f.easy_apply:
        where_parts.append("is_easy_apply = 1")

    if f.work_type and f.work_type != "all":
        where_parts.append("work_type = ?")
        params.append(f.work_type)

    if f.company:
        where_parts.append("company LIKE ?")
        params.append(f"%{f.company}%")

    if f.country == "national":
        where_parts.append("country = 'Brazil'")
    elif f.country == "international":
        where_parts.append("country != 'Brazil'")
        where_parts.append("country != ''")

    if f.max_age_days and f.max_age_days > 0:
        cutoff_ts = int(time.time()) - (f.max_age_days * 86_400)
        where_parts.append(
            "((listed_at_ts > 0 AND listed_at_ts >= ?) "
            "OR (listed_at_ts = 0 AND created_at >= datetime(?, 'unixepoch')))"
        )
        params.append(cutoff_ts)
        params.append(cutoff_ts)

    where_clause = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    # Ordenação — apenas valores controlados, seguros para interpolação
    order_by = (
        "score DESC, created_at DESC"
        if f.sort == "score"
        else "listed_at_ts DESC, created_at DESC"
    )

    cursor = conn.execute(
        f"SELECT * FROM jobs {where_clause} ORDER BY {order_by}",
        params,
    )
    return [row_to_job(r) for r in cursor.fetchall()]


def export_csv(
    conn: sqlite3.Connection,
    path: str | Path,
    job_filter: JobFilter | None = None,
) -> None:
    """Exporta jobs filtrados para CSV."""
    jobs = get_filtered_jobs(conn, job_filter)
    fieldnames = [
        "job_id", "title", "company", "location", "country", "link",
        "score", "work_type", "is_easy_apply", "has_salary",
        "salary_min", "salary_max", "salary_currency",
        "matched_skills", "missing_skills",
        "seniority_match", "summary", "query_source",
    ]
    with open(str(path), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for job in jobs:
            writer.writerow({
                "job_id": job.job_id,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "country": job.country,
                "link": job.link,
                "score": job.score if job.score is not None else "",
                "work_type": job.work_type,
                "is_easy_apply": "yes" if job.is_easy_apply else "no",
                "has_salary": "yes" if job.has_salary else "no",
                "salary_min": job.salary_min or "",
                "salary_max": job.salary_max or "",
                "salary_currency": job.salary_currency,
                "matched_skills": ", ".join(job.matched_skills),
                "missing_skills": ", ".join(job.missing_skills),
                "seniority_match": job.seniority_match,
                "summary": job.summary,
                "query_source": job.query_source,
            })

