"""
Modelos de dados para o LinkedIn Job Matcher V2.
"""

from dataclasses import dataclass, field


@dataclass
class JobResult:
    """Representa uma vaga coletada e (opcionalmente) analisada."""
    job_id: str
    title: str = ""
    company: str = ""
    location: str = ""
    link: str = ""
    description: str = ""
    score: int | None = None
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    summary: str = ""
    seniority_match: str = ""
    query_source: str = ""
