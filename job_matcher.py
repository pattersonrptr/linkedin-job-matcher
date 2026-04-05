"""
LinkedIn Job Matcher com IA (Gemini)
=====================================
Busca vagas no LinkedIn via linkedin-jobs-api (open source) e usa o
Gemini para avaliar o match com o seu perfil.
 
Instalação:
    pip install linkedin-jobs-scraper google-generativeai rich
 
Uso:
    python job_matcher.py
 
Configuração:
    Edite as variáveis em CONFIG e MY_PROFILE abaixo.
"""
 
import time
import json
import os
import re
from dataclasses import dataclass, field
from typing import Optional
import google.generativeai as genai
from linkedin_jobs_scraper import LinkedinScraper
from linkedin_jobs_scraper.events import Events, EventData, EventMetrics
from linkedin_jobs_scraper.filters import (
    RelevanceFilters, TimeFilters, TypeFilters, ExperienceLevelFilters, RemoteFilters
)
from linkedin_jobs_scraper.query import Query, QueryOptions, QueryFilters
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
 
console = Console()
 
# ─────────────────────────────────────────────
# CONFIGURAÇÃO — edite aqui
# ─────────────────────────────────────────────
 
CONFIG = {
    # Sua chave Gemini (ou defina a env var GEMINI_API_KEY)
    # Obtenha grátis em: https://aistudio.google.com/app/apikey
    "gemini_api_key": os.getenv("GEMINI_API_KEY", "SUA_CHAVE_AQUI"),
 
    # Modelo Gemini a usar
    "gemini_model": "gemini-1.5-flash",  # rápido e gratuito
 
    # Score mínimo para aparecer nos resultados (0–10)
    "min_score": 6,
 
    # Quantas vagas buscar por query
    "jobs_per_query": 15,
 
    # Salvar resultados em JSON?
    "save_json": True,
    "output_file": "resultados.json",
 
    # Delay entre chamadas ao Gemini (segundos) — evita rate limit
    "gemini_delay": 1.5,
}
 
# ─────────────────────────────────────────────
# SEU PERFIL — edite aqui
# ─────────────────────────────────────────────
 
_PROFILE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "my_profile.txt")
with open(_PROFILE_FILE, "r", encoding="utf-8") as _f:
    MY_PROFILE = _f.read()
# ─────────────────────────────────────────────
# QUERIES DE BUSCA — ajuste conforme quiser
# ─────────────────────────────────────────────
 
SEARCH_QUERIES = [
    Query(
        query="Python Backend Engineer",
        options=QueryOptions(
            locations=["Brazil", "Remote"],
            apply_link=True,
            filters=QueryFilters(
                relevance=RelevanceFilters.RECENT,
                time=TimeFilters.WEEK,
                type=[TypeFilters.FULL_TIME],
                experience=[
                    ExperienceLevelFilters.MID_SENIOR,
                    ExperienceLevelFilters.SENIOR,
                ],
                remote=[RemoteFilters.REMOTE, RemoteFilters.HYBRID],
            ),
            limit=CONFIG["jobs_per_query"],
        )
    ),
    Query(
        query="Software Engineer Cloud GCP AWS",
        options=QueryOptions(
            locations=["Brazil", "Remote"],
            apply_link=True,
            filters=QueryFilters(
                relevance=RelevanceFilters.RECENT,
                time=TimeFilters.WEEK,
                type=[TypeFilters.FULL_TIME],
                experience=[
                    ExperienceLevelFilters.MID_SENIOR,
                    ExperienceLevelFilters.SENIOR,
                ],
                remote=[RemoteFilters.REMOTE, RemoteFilters.HYBRID],
            ),
            limit=CONFIG["jobs_per_query"],
        )
    ),
    Query(
        query="DevOps Platform Engineer Terraform",
        options=QueryOptions(
            locations=["Brazil", "Remote"],
            apply_link=True,
            filters=QueryFilters(
                relevance=RelevanceFilters.RECENT,
                time=TimeFilters.WEEK,
                type=[TypeFilters.FULL_TIME],
                remote=[RemoteFilters.REMOTE, RemoteFilters.HYBRID],
            ),
            limit=CONFIG["jobs_per_query"],
        )
    ),
]
 
 
# ─────────────────────────────────────────────
# ESTRUTURA DE DADOS
# ─────────────────────────────────────────────
 
@dataclass
class JobResult:
    title: str
    company: str
    location: str
    link: str
    description: str
    score: Optional[int] = None
    matched_skills: list = field(default_factory=list)
    missing_skills: list = field(default_factory=list)
    summary: str = ""
    seniority_match: str = ""
 
 
# ─────────────────────────────────────────────
# COLETA DE VAGAS
# ─────────────────────────────────────────────
 
collected_jobs: list[JobResult] = []
 
def on_data(data: EventData):
    job = JobResult(
        title=data.title or "",
        company=data.company or "",
        location=data.location or "",
        link=data.link or data.apply_link or "",
        description=data.description or "",
    )
    collected_jobs.append(job)
    console.print(f"  [dim]Coletada:[/dim] {job.title} @ {job.company}")
 
def on_error(error):
    console.print(f"[red]Erro no scraper:[/red] {error}")
 
def on_end():
    console.print(f"\n[green]Coleta finalizada.[/green] {len(collected_jobs)} vagas encontradas.")
 
 
def collect_jobs() -> list[JobResult]:
    console.print(Panel("[bold blue]🔍 Coletando vagas do LinkedIn...[/bold blue]"))
 
    scraper = LinkedinScraper(
        chrome_executable_path=None,  # usa chromedriver do PATH
        chrome_binary_location=None,
        chrome_options=None,
        headless=True,
        max_workers=1,
        slow_mo=1.2,
        page_load_timeout=40,
    )
 
    scraper.on(Events.DATA, on_data)
    scraper.on(Events.ERROR, on_error)
    scraper.on(Events.END, on_end)
 
    scraper.run(SEARCH_QUERIES)
    return collected_jobs
 
 
# ─────────────────────────────────────────────
# ANÁLISE COM GEMINI
# ─────────────────────────────────────────────
 
def build_prompt(job: JobResult) -> str:
    return f"""
Você é um especialista em recrutamento técnico. Analise a compatibilidade entre
o candidato abaixo e a vaga de emprego, e retorne APENAS um JSON válido.
 
## PERFIL DO CANDIDATO
{MY_PROFILE}
 
## VAGA
Título: {job.title}
Empresa: {job.company}
Localização: {job.location}
Descrição:
{job.description[:3000]}
 
## INSTRUÇÃO
Retorne SOMENTE este JSON (sem markdown, sem explicação):
{{
  "score": <inteiro de 0 a 10>,
  "matched_skills": ["skill1", "skill2"],
  "missing_skills": ["skill_faltante1"],
  "seniority_match": "exato | acima | abaixo | não informado",
  "summary": "<2-3 frases explicando o match em português>"
}}
 
Critérios para o score:
- 9-10: Match excelente, candidato tem quase tudo
- 7-8: Match muito bom, pequenas lacunas
- 5-6: Match razoável, algumas lacunas relevantes
- 3-4: Match fraco, muitas lacunas
- 0-2: Vaga fora do perfil
"""
 
 
def analyze_with_gemini(jobs: list[JobResult]) -> list[JobResult]:
    console.print(Panel("[bold blue]🤖 Analisando vagas com Gemini...[/bold blue]"))
 
    genai.configure(api_key=CONFIG["gemini_api_key"])
    model = genai.GenerativeModel(CONFIG["gemini_model"])
 
    analyzed = []
    for i, job in enumerate(jobs, 1):
        console.print(f"  [{i}/{len(jobs)}] Analisando: {job.title} @ {job.company}...")
 
        if not job.description.strip():
            console.print("    [yellow]Sem descrição, pulando.[/yellow]")
            continue
 
        try:
            prompt = build_prompt(job)
            response = model.generate_content(prompt)
            raw = response.text.strip()
 
            # Remove possíveis blocos ```json
            raw = re.sub(r"^```json\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
 
            data = json.loads(raw)
            job.score = int(data.get("score", 0))
            job.matched_skills = data.get("matched_skills", [])
            job.missing_skills = data.get("missing_skills", [])
            job.seniority_match = data.get("seniority_match", "")
            job.summary = data.get("summary", "")
 
            analyzed.append(job)
            time.sleep(CONFIG["gemini_delay"])
 
        except json.JSONDecodeError as e:
            console.print(f"    [red]Erro ao parsear JSON do Gemini: {e}[/red]")
            console.print(f"    Resposta recebida: {raw[:200]}")
        except Exception as e:
            console.print(f"    [red]Erro inesperado: {e}[/red]")
 
    return analyzed
 
 
# ─────────────────────────────────────────────
# EXIBIÇÃO DOS RESULTADOS
# ─────────────────────────────────────────────
 
def score_color(score: int) -> str:
    if score >= 8:
        return "green"
    elif score >= 6:
        return "yellow"
    return "red"
 
 
def display_results(jobs: list[JobResult]):
    filtered = [j for j in jobs if j.score is not None and j.score >= CONFIG["min_score"]]
    filtered.sort(key=lambda j: j.score, reverse=True)
 
    console.print(f"\n[bold]✅ {len(filtered)} vagas acima do score mínimo ({CONFIG['min_score']})[/bold]\n")
 
    table = Table(
        title="🎯 Vagas com Melhor Match",
        box=box.ROUNDED,
        show_lines=True,
        header_style="bold cyan",
    )
    table.add_column("Score", width=7, justify="center")
    table.add_column("Vaga", min_width=30)
    table.add_column("Empresa", min_width=20)
    table.add_column("Localização", min_width=15)
    table.add_column("Skills ✓", min_width=20)
    table.add_column("Skills ✗", min_width=15)
    table.add_column("Seniority", width=12)
 
    for job in filtered:
        color = score_color(job.score)
        table.add_row(
            Text(f"{job.score}/10", style=f"bold {color}"),
            f"[link={job.link}]{job.title}[/link]",
            job.company,
            job.location,
            ", ".join(job.matched_skills[:5]) or "—",
            ", ".join(job.missing_skills[:3]) or "—",
            job.seniority_match,
        )
 
    console.print(table)
 
    # Detalhes das top 5
    console.print("\n[bold cyan]── Detalhes das Top 5 ──[/bold cyan]\n")
    for job in filtered[:5]:
        color = score_color(job.score)
        console.print(Panel(
            f"[bold]{job.title}[/bold] @ {job.company}\n"
            f"[dim]{job.location}[/dim]\n\n"
            f"[{color}]Score: {job.score}/10[/{color}]  |  Seniority: {job.seniority_match}\n\n"
            f"✅ [green]{', '.join(job.matched_skills)}[/green]\n"
            f"❌ [red]{', '.join(job.missing_skills) or 'nenhuma lacuna crítica'}[/red]\n\n"
            f"📝 {job.summary}\n\n"
            f"🔗 {job.link}",
            expand=False,
        ))
 
 
# ─────────────────────────────────────────────
# SALVAR JSON
# ─────────────────────────────────────────────
 
def save_results(jobs: list[JobResult]):
    output = []
    for j in jobs:
        if j.score is not None:
            output.append({
                "score": j.score,
                "title": j.title,
                "company": j.company,
                "location": j.location,
                "link": j.link,
                "matched_skills": j.matched_skills,
                "missing_skills": j.missing_skills,
                "seniority_match": j.seniority_match,
                "summary": j.summary,
            })
 
    output.sort(key=lambda x: x["score"], reverse=True)
 
    with open(CONFIG["output_file"], "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
 
    console.print(f"\n💾 Resultados salvos em [bold]{CONFIG['output_file']}[/bold]")
 
 
# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
 
def main():
    console.print(Panel(
        "[bold white]LinkedIn Job Matcher com IA[/bold white]\n"
        "[dim]Busca vagas e avalia match com seu perfil usando Gemini[/dim]",
        style="blue",
    ))
 
    if CONFIG["gemini_api_key"] == "SUA_CHAVE_AQUI":
        console.print("[red bold]❌ Configure sua GEMINI_API_KEY antes de rodar![/red bold]")
        console.print("   Obtenha grátis em: https://aistudio.google.com/app/apikey")
        console.print("   Depois: export GEMINI_API_KEY='sua_chave'  ou edite CONFIG no script")
        return
 
    # 1. Coletar vagas
    jobs = collect_jobs()
 
    if not jobs:
        console.print("[yellow]Nenhuma vaga coletada. Verifique o chromedriver e conexão.[/yellow]")
        return
 
    # 2. Analisar com Gemini
    analyzed = analyze_with_gemini(jobs)
 
    # 3. Exibir resultados
    display_results(analyzed)
 
    # 4. Salvar JSON
    if CONFIG["save_json"]:
        save_results(analyzed)
 
 
if __name__ == "__main__":
    main()
