"""
Scraper LinkedIn usando linkedin-api (session-based, sem browser).
Integra anti_block.py para delays e coleta de vagas com deduplicação global.
"""

import logging
import time

import requests
from linkedin_api import Linkedin
from tqdm import tqdm

from anti_block import RateLimiter
from models import JobResult

logger = logging.getLogger(__name__)

# Mapeamento de workplace type URN para string legível
_WORKPLACE_TYPE_MAP: dict[str, str] = {
    "1": "onsite",
    "2": "remote",
    "3": "hybrid",
}

# Strings de localização que não representam um país
_NON_COUNTRY_TOKENS = {"remote", "worldwide", "global", "anywhere", ""}


def _parse_country(formatted_location: str) -> str:
    """Extrai o país de uma string de localização do LinkedIn.

    Exemplos:
        "São Paulo, Brazil"        → "Brazil"
        "United States"            → "United States"
        "Remote"                   → ""
    """
    if not formatted_location:
        return ""
    parts = [p.strip() for p in formatted_location.split(",")]
    candidate = parts[-1]
    if candidate.lower() in _NON_COUNTRY_TOKENS:
        return ""
    return candidate


def _parse_work_type(workplace_types: list) -> str:
    """Converte a lista de URNs de workplace type para string normalizada."""
    if not workplace_types:
        return ""
    urn = workplace_types[0]
    type_id = str(urn).split(":")[-1]
    return _WORKPLACE_TYPE_MAP.get(type_id, "")


def _parse_easy_apply(apply_method: dict) -> bool:
    """Retorna True se a vaga usa Easy Apply do LinkedIn."""
    if not apply_method:
        return False
    # Easy Apply usa a chave ComplexOnsiteApply
    return any("ComplexOnsiteApply" in k for k in apply_method)


def _parse_salary(details: dict) -> tuple[bool, int | None, int | None, str]:
    """Extrai informações salariais. Retorna (has_salary, min, max, currency)."""
    salary_data = details.get("salary")
    if not salary_data:
        return False, None, None, ""
    salary_min = salary_data.get("minValue") or salary_data.get("min")
    salary_max = salary_data.get("maxValue") or salary_data.get("max")
    currency = salary_data.get("currencyCode") or salary_data.get("currency", "")
    has_salary = bool(salary_min or salary_max)
    return has_salary, salary_min, salary_max, currency.upper() if currency else ""


class LinkedInScraper:
    """Wrapper para linkedin-api com anti-blocking integrado."""

    def __init__(
        self,
        li_at: str,
        jsessionid: str,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        cookies = requests.cookies.RequestsCookieJar()
        cookies.set("li_at", li_at)
        cookies.set("JSESSIONID", jsessionid)
        self._api = Linkedin(
            username="",
            password="",
            authenticate=True,
            cookies=cookies,
        )
        self._limiter = rate_limiter or RateLimiter()
        # IDs já coletados nesta sessão (dedup global)
        self._seen_ids: set[str] = set()

    def _apply_delay(self) -> None:
        """Aplica delay entre requisições."""
        delay = self._limiter.get_delay()
        time.sleep(delay)

    def search_jobs(
        self,
        queries_config: list[dict],
        max_jobs: int = 30,
        listed_at: int = 604800,
        skip_closed: bool = True,
    ) -> list[JobResult]:
        """
        Executa as queries configuradas e retorna lista de JobResult.
        Cada item do queries_config é um dict com:
            query, location, experience, job_type, remote

        Deduplicação global por entityUrn. Respeita max_jobs total.

        Args:
            skip_closed: se True (padrão), ignora vagas com jobState != "LISTED"
        """
        results: list[JobResult] = []
        total_queries = len(queries_config)

        for qi, qc in enumerate(queries_config, 1):
            query_text = qc["query"]
            location = qc.get("location", "")
            experience = qc.get("experience", [])
            job_type = qc.get("job_type", [])
            remote = qc.get("remote", [])

            remaining = max_jobs - len(results)
            if remaining <= 0:
                break

            # linkedin-api: search_jobs retorna lista de dicts
            # limit = quanto buscar nesta query específica
            limit = min(remaining, 20)  # batches de 20, respeitando o teto restante

            logger.info(
                "Buscando query %d/%d: %s (location=%s, limit=%d)",
                qi, total_queries, query_text, location, limit,
            )

            try:
                job_search_results = self._api.search_jobs(
                    keywords=query_text,
                    location_name=location if location else None,
                    experience=experience,
                    job_type=job_type,
                    remote=remote,
                    listed_at=listed_at,
                    limit=limit,
                )
            except Exception as exc:
                logger.error("Erro na busca '%s': %s", query_text, exc)
                continue

            for item in job_search_results:
                # entityUrn é o ID único do job
                job_id = item.get("entityUrn", "") or item.get("trackingUrn", "")
                if not job_id:
                    continue

                # Remover prefixo se presente (ex: urn:li:fs_normalized_jobPosting:...)
                numeric_id = job_id.split(":")[-1] if ":" in job_id else job_id

                if numeric_id in self._seen_ids:
                    continue  # dedup global

                if len(results) >= max_jobs:
                    break

                self._seen_ids.add(numeric_id)

                # Buscar detalhes completos
                try:
                    details = self._api.get_job(numeric_id)
                except Exception as exc:
                    logger.warning("Erro ao buscar detalhes do job %s: %s", numeric_id, exc)
                    continue

                # ── Status da vaga ──
                job_state = details.get("jobState", "LISTED")
                is_closed = job_state != "LISTED"
                if skip_closed and is_closed:
                    logger.info("  Pulando vaga fechada: %s", numeric_id)
                    continue

                # ── Empresa ──
                title = details.get("title", "")
                company_name = ""
                company_details = details.get("companyDetails", {})
                if company_details:
                    # A API retorna companyDetails com uma chave dinâmica (namespace voyager)
                    # que encapsula o objeto com companyResolutionResult.name
                    cd_key = next(iter(company_details), None)
                    if cd_key:
                        company_name = (
                            company_details[cd_key]
                            .get("companyResolutionResult", {})
                            .get("name", "")
                        )

                # ── Localização e país ──
                # formattedLocation é o campo correto na versão atual da API
                location_str = details.get("formattedLocation", "") or details.get("locationName", "") or ""
                country = _parse_country(location_str)

                # ── Tipo de trabalho ──
                work_type = _parse_work_type(details.get("workplaceTypes", []))
                if not work_type and details.get("workRemoteAllowed"):
                    work_type = "remote"

                # ── Easy Apply ──
                is_easy_apply = _parse_easy_apply(details.get("applyMethod", {}))

                # ── Salário ──
                has_salary, salary_min, salary_max, salary_currency = _parse_salary(details)

                # ── Timestamp de postagem ──
                listed_at_ms = details.get("listedAt", 0) or 0
                listed_at_ts = int(listed_at_ms) // 1000  # milissegundos → segundos

                # ── Descrição ──
                job_link = f"https://www.linkedin.com/jobs/view/{numeric_id}"
                desc = details.get("description", "")
                if isinstance(desc, dict):
                    desc = desc.get("text", "") or ""

                job = JobResult(
                    job_id=numeric_id,
                    title=title,
                    company=company_name,
                    location=location_str,
                    country=country,
                    link=job_link,
                    description=desc,
                    query_source=query_text,
                    is_closed=is_closed,
                    is_easy_apply=is_easy_apply,
                    work_type=work_type,
                    has_salary=has_salary,
                    salary_min=salary_min,
                    salary_max=salary_max,
                    salary_currency=salary_currency,
                    listed_at_ts=listed_at_ts,
                )
                results.append(job)

                logger.info("  Coletada: %s @ %s [%s]", title, company_name, work_type or "?")
                self._apply_delay()

            # Delay extra entre queries
            if qi < total_queries:
                self._apply_delay()

        return results



class LinkedInScraper:
    """Wrapper para linkedin-api com anti-blocking integrado."""

    def __init__(
        self,
        li_at: str,
        jsessionid: str,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        cookies = requests.cookies.RequestsCookieJar()
        cookies.set("li_at", li_at)
        cookies.set("JSESSIONID", jsessionid)
        self._api = Linkedin(
            username="",
            password="",
            authenticate=True,
            cookies=cookies,
        )
        self._limiter = rate_limiter or RateLimiter()
        # IDs já coletados nesta sessão (dedup global)
        self._seen_ids: set[str] = set()

    def _apply_delay(self) -> None:
        """Aplica delay entre requisições."""
        delay = self._limiter.get_delay()
        time.sleep(delay)

    def search_jobs(
        self,
        queries_config: list[dict],
        max_jobs: int = 30,
        listed_at: int = 604800,
    ) -> list[JobResult]:
        """
        Executa as queries configuradas e retorna lista de JobResult.
        Cada item do queries_config é um dict com:
            query, location, experience, job_type, remote

        Deduplicação global por entityUrn. Respeita max_jobs total.
        """
        results: list[JobResult] = []
        total_queries = len(queries_config)

        for qi, qc in enumerate(queries_config, 1):
            query_text = qc["query"]
            location = qc.get("location", "")
            experience = qc.get("experience", [])
            job_type = qc.get("job_type", [])
            remote = qc.get("remote", [])

            remaining = max_jobs - len(results)
            if remaining <= 0:
                break

            # linkedin-api: search_jobs retorna lista de dicts
            # limit = quanto buscar nesta query específica
            limit = min(remaining, 20)  # batches de 20, respeitando o teto restante

            logger.info(
                "Buscando query %d/%d: %s (location=%s, limit=%d)",
                qi, total_queries, query_text, location, limit,
            )

            try:
                job_search_results = self._api.search_jobs(
                    keywords=query_text,
                    location_name=location if location else None,
                    experience=experience,
                    job_type=job_type,
                    remote=remote,
                    listed_at=listed_at,
                    limit=limit,
                )
            except Exception as exc:
                logger.error("Erro na busca '%s': %s", query_text, exc)
                continue

            for item in job_search_results:
                # entityUrn é o ID único do job
                job_id = item.get("entityUrn", "") or item.get("trackingUrn", "")
                if not job_id:
                    continue

                # Remover prefixo se presente (ex: urn:li:fs_normalized_jobPosting:...)
                numeric_id = job_id.split(":")[-1] if ":" in job_id else job_id

                if numeric_id in self._seen_ids:
                    continue  # dedup global

                if len(results) >= max_jobs:
                    break

                self._seen_ids.add(numeric_id)

                # Buscar detalhes completos
                try:
                    details = self._api.get_job(numeric_id)
                except Exception as exc:
                    logger.warning("Erro ao buscar detalhes do job %s: %s", numeric_id, exc)
                    continue

                title = details.get("title", "")
                company_name = ""
                company_details = details.get("companyDetails", {})
                if company_details:
                    # A API retorna companyDetails com uma chave dinâmica (namespace voyager)
                    # que encapsula o objeto com companyResolutionResult.name
                    cd_key = next(iter(company_details), None)
                    if cd_key:
                        company_name = (
                            company_details[cd_key]
                            .get("companyResolutionResult", {})
                            .get("name", "")
                        )
                # formattedLocation é o campo correto na versão atual da API
                location_str = details.get("formattedLocation", "") or details.get("locationName", "") or ""
                job_link = f"https://www.linkedin.com/jobs/view/{numeric_id}"
                # linkedin-api retorna description como str ou dict
                desc = details.get("description", "")
                if isinstance(desc, dict):
                    desc = desc.get("text", "") or ""

                job = JobResult(
                    job_id=numeric_id,
                    title=title,
                    company=company_name,
                    location=location_str,
                    link=job_link,
                    description=desc,
                    query_source=query_text,
                )
                results.append(job)

                logger.info("  Coletada: %s @ %s", title, company_name)
                self._apply_delay()

            # Delay extra entre queries
            if qi < total_queries:
                self._apply_delay()

        return results
