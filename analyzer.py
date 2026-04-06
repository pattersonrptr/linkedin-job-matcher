"""
Análise de vagas com LLM para o LinkedIn Job Matcher V2.
Montagem de prompts, análise individual e em batch com delays e progresso.
"""

import logging

from tqdm import tqdm

from anti_block import RateLimiter
from llm import LLMClient
from models import JobResult

logger = logging.getLogger(__name__)

ANALYSIS_SYSTEM_PROMPT = """\
Você é um especialista em recrutamento técnico com 20 anos de experiência \
em engenharia de software. Sua tarefa é analisar a compatibilidade entre \
o candidato descrito e a vaga de emprego fornecida.

Retorne APENAS um JSON válido com a seguinte estrutura:
{
  "score": <inteiro de 0 a 10>,
  "matched_skills": ["skill1", "skill2"],
  "missing_skills": ["skill_faltante1"],
  "seniority_match": "exato | acima | abaixo | não informado",
  "summary": "<2-3 frases explicando o match em portugues>"
}

Critérios para o score:
- 9-10: Match excelente, candidato tem quase todos os requisitos
- 7-8: Match muito bom, pequenas lacunas preenchíveis
- 5-6: Match razoável, algumas lacunas relevantes
- 3-4: Match fraco, muitas lacunas importantes
- 0-2: Vaga muito fora do perfil do candidato

Considere:
- Overlap de stack técnica (linguagens, frameworks, ferramentas)
- Senioridade e anos de experiência
- Tipo de trabalho e responsabilidades
- Tecnologias que são diferencial vs obrigatórias
"""


def build_prompt(profile_text: str, job: JobResult) -> str:
    """Monta o prompt completo para análise de uma vaga."""
    desc = job.description
    # Não cortar — modelos modernos aceitam descrições longas
    # mas se for absurdamente grande, limitar a 12000 chars
    if len(desc) > 12000:
        desc = desc[:12000] + "\n\n... (descrição truncada por tamanho)"

    return (
        f"{ANALYSIS_SYSTEM_PROMPT}\n\n"
        f"## PERFIL DO CANDIDATO\n{profile_text}\n\n"
        f"## VAGA\n"
        f"ID: {job.job_id}\n"
        f"Título: {job.title}\n"
        f"Empresa: {job.company}\n"
        f"Localização: {job.location}\n"
        f"Link: {job.link}\n"
        f"Descrição:\n{desc}\n\n"
        f"Retorne APENAS o JSON conforme instruído."
    )


class JobAnalyzer:
    """Orquestra a análise de vagas usando o cliente LLM."""

    def __init__(
        self,
        llm: LLMClient,
        profile_text: str,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self._llm = llm
        self._profile = profile_text
        self._limiter = rate_limiter or RateLimiter()

    def analyze(self, job: JobResult) -> JobResult:
        """Analisa uma única vaga e popula os campos de resultado."""
        if not job.description.strip():
            logger.info("Job %s sem descrição, pulando análise.", job.job_id)
            return job

        prompt = build_prompt(self._profile, job)
        data = self._llm.analyze_job(prompt)

        if data is None:
            logger.warning("Falha ao analisar job %s — LLM não retornou JSON válido.", job.job_id)
            return job

        job.score = int(data.get("score", 0))
        job.matched_skills = data.get("matched_skills", [])
        job.missing_skills = data.get("missing_skills", [])
        job.seniority_match = data.get("seniority_match", "")
        job.summary = data.get("summary", "")

        # Reseta backoff se teve sucesso
        self._limiter.reset_backoff()

        return job

    def analyze_batch(
        self, jobs: list[JobResult]
    ) -> list[JobResult]:
        """
        Analisa um lote de jobs com barra de progresso e delays configuráveis.
        Retorna lista de jobs analisados (com score populado).
        """
        analyzed: list[JobResult] = []

        for job in tqdm(jobs, desc="Analisando vagas", unit="job"):
            job = self.analyze(job)

            if job.score is not None:
                analyzed.append(job)
                logger.info(
                    "  Score %d/10 — %s @ %s",
                    job.score, job.title, job.company,
                )
            else:
                logger.warning(
                    "  Falha na análise — %s @ %s",
                    job.title, job.company,
                )

            # Delay entre análises
            self._limiter.wait()

            # Cooldown periódico
            if self._limiter.after_n_jobs():
                logger.info("  Aguardando cooldown longo...")
                self._limiter.wait_cooldown()

        return analyzed
