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
    country: str = ""            # extraído de formattedLocation
    link: str = ""
    description: str = ""
    score: int | None = None
    matched_skills: list[str] = field(default_factory=list)
    familiar_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    summary: str = ""
    seniority_match: str = ""
    query_source: str = ""
    # ── Campos de status e tipo ──
    is_closed: bool = False      # True se jobState != "LISTED"
    is_easy_apply: bool = False  # True se applyMethod for ComplexOnsiteApply
    work_type: str = ""          # "remote" | "hybrid" | "onsite" | ""
    # ── Campos de salário ──
    has_salary: bool = False
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str = ""    # "USD" | "BRL" | "EUR" | ""
    # ── Metadata ──
    listed_at_ts: int = 0        # unix timestamp em segundos (da API do LinkedIn)


@dataclass
class JobFilter:
    """Parâmetros de filtro para consulta e exibição de vagas."""
    min_score: int = 0
    country: str = "all"             # "national" | "international" | "all"
    has_salary: bool = False         # se True, só vagas com salário divulgado
    min_salary: int | None = None    # valor mínimo (na moeda de salary_currency)
    currency: str = ""               # "USD" | "BRL" | "EUR" | "" (qualquer)
    easy_apply: bool = False         # se True, só Easy Apply
    work_type: str = "all"           # "remote" | "hybrid" | "onsite" | "all"
    company: str = ""                # substring match (case-insensitive)
    sort: str = "score"              # "score" | "date"
    max_age_days: int | None = None  # exibir apenas vagas dos últimos N dias
