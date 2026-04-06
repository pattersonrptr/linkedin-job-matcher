"""
Operações de banco de dados SQLite para o LinkedIn Job Matcher V2.
Upsert, consulta, filtros e exportação CSV.
"""

import csv
import json
import sqlite3
from pathlib import Path

from models import JobResult

# Cria a tabela jobs com os campos necessários
_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT,
    link TEXT,
    description TEXT,
    score INTEGER,
    matched_skills TEXT,
    missing_skills TEXT,
    seniority_match TEXT,
    summary TEXT,
    query_source TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def init_db(db_path: str | Path = "job_matcher.db") -> sqlite3.Connection:
    """Inicializa o banco SQLite e retorna a conexão."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    conn.commit()
    return conn


def job_to_row(job: JobResult) -> dict:
    """Converte JobResult em dicionário para SQL."""
    return {
        "job_id": job.job_id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "link": job.link,
        "description": job.description,
        "score": job.score,
        "matched_skills": json.dumps(job.matched_skills, ensure_ascii=False),
        "missing_skills": json.dumps(job.missing_skills, ensure_ascii=False),
        "seniority_match": job.seniority_match,
        "summary": job.summary,
        "query_source": job.query_source,
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

    return JobResult(
        job_id=str(row["job_id"]),
        title=str(row["title"]),
        company=str(row["company"]),
        location=str(row["location"] or ""),
        link=str(row["link"] or ""),
        description=str(row["description"] or ""),
        score=row["score"],
        matched_skills=_loads(row["matched_skills"]),
        missing_skills=_loads(row["missing_skills"]),
        seniority_match=str(row["seniority_match"] or ""),
        summary=str(row["summary"] or ""),
        query_source=str(row["query_source"] or ""),
    )


def upsert_job(conn: sqlite3.Connection, job: JobResult) -> None:
    """Insere ou atualiza um job pelo job_id (ON CONFLICT)."""
    row = job_to_row(job)
    conn.execute(
        """
        INSERT INTO jobs (
            job_id, title, company, location, link, description,
            score, matched_skills, missing_skills, seniority_match,
            summary, query_source
        ) VALUES (
            :job_id, :title, :company, :location, :link, :description,
            :score, :matched_skills, :missing_skills, :seniority_match,
            :summary, :query_source
        )
        ON CONFLICT(job_id) DO UPDATE SET
            title = excluded.title,
            company = excluded.company,
            location = excluded.location,
            link = excluded.link,
            description = excluded.description,
            score = excluded.score,
            matched_skills = excluded.matched_skills,
            missing_skills = excluded.missing_skills,
            seniority_match = excluded.seniority_match,
            summary = excluded.summary,
            query_source = excluded.query_source,
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
    cursor = conn.execute(
        "SELECT job_id FROM jobs WHERE score IS NOT NULL"
    )
    return {str(r["job_id"]) for r in cursor.fetchall()}


def get_collected_job_ids(conn: sqlite3.Connection) -> set[str]:
    """Retorna set de todos os job_ids coletados (com ou sem análise)."""
    cursor = conn.execute("SELECT job_id FROM jobs")
    return {str(r["job_id"]) for r in cursor.fetchall()}


def get_filtered_jobs(conn: sqlite3.Connection, min_score: int = 0) -> list[JobResult]:
    """Retorna jobs com score >= min_score, ordenados por score descendente."""
    cursor = conn.execute(
        "SELECT * FROM jobs WHERE score >= ? ORDER BY score DESC, created_at DESC",
        (min_score,),
    )
    return [row_to_job(r) for r in cursor.fetchall()]


def export_csv(conn: sqlite3.Connection, path: str | Path, min_score: int = 0) -> None:
    """Exporta jobs filtrados para CSV."""
    jobs = get_filtered_jobs(conn, min_score)
    fieldnames = [
        "job_id", "title", "company", "location", "link",
        "score", "matched_skills", "missing_skills",
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
                "link": job.link,
                "score": job.score if job.score is not None else "",
                "matched_skills": ", ".join(job.matched_skills),
                "missing_skills": ", ".join(job.missing_skills),
                "seniority_match": job.seniority_match,
                "summary": job.summary,
                "query_source": job.query_source,
            })
