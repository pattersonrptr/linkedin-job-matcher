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
