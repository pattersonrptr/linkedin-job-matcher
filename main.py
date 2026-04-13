"""
LinkedIn Job Matcher V2 — Entry point.
CLI com argparse, carregamento de config.toml e .env, fluxo completo
de coleta, análise, exibição e exportação.
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Força UTF-8 no stdout/stderr para evitar UnicodeEncodeError em terminais cp1252 (Windows)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[import-not-found]

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from rich.progress import Progress, SpinnerColumn, TextColumn
from tqdm import tqdm

from analyzer import JobAnalyzer
from anti_block import RateLimiter
from llm import LLMClient
from models import JobFilter, JobResult
from scraper import LinkedInScraper
from session_manager import get_linkedin_cookies
from storage import (
    export_csv,
    get_all_jobs,
    get_analyzed_job_ids,
    get_collected_job_ids,
    get_filtered_jobs,
    init_db,
    upsert_job,
)

console = Console()
logger = logging.getLogger("linkedin_matcher")

BASE_DIR = Path(__file__).resolve().parent

# Mapeamento de --date-posted para seconds (listed_at da API)
_DATE_POSTED_MAP: dict[str, int] = {
    "24h":   86_400,
    "week":  604_800,
    "month": 2_592_000,
    "any":   0,  # sem filtro de data
}


# ─────────────────────────────────────────────
# Carregamento de configuração
# ─────────────────────────────────────────────

def load_config(config_path: str | Path) -> dict:
    """Carrega config.toml e retorna dict."""
    path = Path(config_path)
    if not path.exists():
        console.print(f"[red]Config não encontrado: {path}[/red]")
        sys.exit(1)
    with open(path, "rb") as f:
        return tomllib.load(f)


def load_profile(profile_path: str | Path) -> str:
    """Carrega o perfil do candidato."""
    path = Path(profile_path)
    if not path.exists():
        console.print(f"[red]Perfil não encontrado: {path}[/red]")
        sys.exit(1)
    return path.read_text(encoding="utf-8")


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="LinkedIn Job Matcher V2 — Busca e avalia vagas com IA",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python main.py                                  # Busca + análise completa
  python main.py --scrape-only --max-jobs 50      # Só coleta
  python main.py --analyze-only                   # Só analisa o que está no banco
  python main.py --show --work-type remote        # Mostra vagas remotas
  python main.py --show --country international --min-score 7
  python main.py --show --has-salary --currency USD --sort date
  python main.py --export vagas.csv --min-score 6
        """,
    )

    # ── Configuração ──
    parser.add_argument("--config", default="config.toml",
                        help="Caminho do config.toml (default: config.toml)")
    parser.add_argument("--profile", default=None,
                        help="Caminho do arquivo de perfil (default: my_profile.txt)")
    parser.add_argument("--db", default="job_matcher.db",
                        help="Caminho do banco SQLite (default: job_matcher.db)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Log detalhado")

    # ── Modos de execução ──
    mode = parser.add_argument_group("Modos de execução")
    mode.add_argument("--show", action="store_true",
                      help="Mostra resultados já salvos no banco (sem scraping)")
    mode.add_argument("--resume", action="store_true",
                      help="Retoma busca, pulando vagas já coletadas/analisadas")
    mode.add_argument("--scrape-only", action="store_true",
                      help="Apenas coleta vagas, sem análise LLM")
    mode.add_argument("--analyze-only", action="store_true",
                      help="Apenas analisa vagas já coletadas no banco")
    mode.add_argument("--export", nargs="?", const="resultados.csv", default=None,
                      metavar="PATH",
                      help="Exporta resultados filtrados para CSV (default: resultados.csv)")

    # ── Overrides de coleta ──
    collect = parser.add_argument_group("Opções de coleta")
    collect.add_argument("--max-jobs", type=int, default=None,
                         help="Número máximo de vagas a coletar")
    collect.add_argument("--date-posted",
                         choices=["any", "24h", "week", "month"], default=None,
                         help="Filtrar por data de postagem durante a coleta")
    collect.add_argument("--skip-closed", action="store_true", default=True,
                         help="Ignorar vagas fechadas (padrão: ativado)")
    collect.add_argument("--no-skip-closed", dest="skip_closed", action="store_false",
                         help="Incluir vagas fechadas")

    # ── Filtros de exibição / show ──
    filters = parser.add_argument_group("Filtros de exibição")
    filters.add_argument("--min-score", type=int, default=None,
                         help="Score mínimo para exibir (override do config)")
    filters.add_argument("--country",
                         choices=["national", "international", "all"], default="all",
                         help="Filtrar por origem: national=Brasil, international=fora do Brasil")
    filters.add_argument("--work-type",
                         choices=["remote", "hybrid", "onsite", "all"], default="all",
                         help="Filtrar por tipo de trabalho")
    filters.add_argument("--has-salary", action="store_true",
                         help="Mostrar apenas vagas com salário divulgado")
    filters.add_argument("--min-salary", type=int, default=None,
                         help="Salário mínimo (use com --currency para especificar moeda)")
    filters.add_argument("--currency", default="",
                         metavar="CODE",
                         help="Moeda do salário: USD, BRL, EUR, etc.")
    filters.add_argument("--easy-apply", action="store_true",
                         help="Mostrar apenas vagas com Easy Apply")
    filters.add_argument("--company", default="",
                         metavar="NOME",
                         help="Filtrar por nome de empresa (substring, case-insensitive)")
    filters.add_argument("--sort",
                         choices=["score", "date"], default="score",
                         help="Ordenar por score (padrão) ou data de postagem")

    return parser.parse_args()


def build_job_filter(args: argparse.Namespace, min_score: int) -> JobFilter:
    """Constrói JobFilter a partir dos args da CLI."""
    return JobFilter(
        min_score=args.min_score if args.min_score is not None else min_score,
        country=args.country,
        has_salary=args.has_salary,
        min_salary=args.min_salary,
        currency=args.currency.upper() if args.currency else "",
        easy_apply=args.easy_apply,
        work_type=args.work_type,
        company=args.company,
        sort=args.sort,
    )


# ─────────────────────────────────────────────
# Fluxo principal
# ─────────────────────────────────────────────

def run_full(
    cfg: dict,
    profile_text: str,
    db_path: str,
    args: argparse.Namespace,
    env_path: Path | None = None,
) -> None:
    """Executa o fluxo completo: coleta, análise, exibição."""

    scraper_cfg = cfg["scraper"]
    llm_cfg = cfg["llm"]
    app_cfg = cfg["app"]
    queries_cfg = cfg["queries"]

    max_jobs = scraper_cfg.get("max_jobs", 30)
    if args.max_jobs is not None:
        max_jobs = args.max_jobs

    # listed_at: --date-posted sobrescreve o config.toml
    listed_at = scraper_cfg.get("listed_at", 604800)
    if args.date_posted:
        override = _DATE_POSTED_MAP[args.date_posted]
        listed_at = override if override > 0 else listed_at

    min_score = app_cfg.get("min_score", 6)
    job_filter = build_job_filter(args, min_score)

    conn = init_db(db_path)

    rate_limiter = RateLimiter(
        delay_min=scraper_cfg.get("delay_min", 2.0),
        delay_max=scraper_cfg.get("delay_max", 5.0),
        cooldown_after=scraper_cfg.get("cooldown_after", 10),
        cooldown_min=scraper_cfg.get("cooldown_seconds_min", 30),
        cooldown_max=scraper_cfg.get("cooldown_seconds_max", 120),
    )

    llm_api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not llm_api_key:
        console.print("[red bold]OPENROUTER_API_KEY não definida no .env![/red bold]")
        sys.exit(1)

    # OPENROUTER_MODEL no .env tem prioridade sobre config.toml
    llm_model = os.getenv("OPENROUTER_MODEL") or llm_cfg.get("model", "qwen/qwen2.5-72b-instruct")

    # ── Modo analyze-only ──
    if args.analyze_only:
        console.print(Panel("[bold yellow]Modo analyze-only — analisando vagas já coletadas[/bold yellow]"))
        stored_jobs = get_all_jobs(conn)
        not_analyzed = [j for j in stored_jobs if j.score is None]
        if not_analyzed:
            console.print(f"[dim]{len(not_analyzed)} vagas pendentes de análise.[/dim]")
            llm = LLMClient(
                api_key=llm_api_key,
                model=llm_model,
                max_tokens=llm_cfg.get("max_tokens", 1024),
                temperature=llm_cfg.get("temperature", 0.3),
                timeout=llm_cfg.get("timeout", 30),
            )
            analyzer = JobAnalyzer(llm, profile_text, rate_limiter)
            analyze_and_store(analyzer, not_analyzed, conn)
        else:
            console.print("[green]Todas as vagas já foram analisadas.[/green]")
        display_from_db(conn, job_filter)
        return

    # ── Scraping ──
    try:
        li_at, jsessionid = get_linkedin_cookies(env_path=env_path)
    except (EnvironmentError, TimeoutError, ValueError) as exc:
        console.print(f"[red bold]Erro ao obter sessão LinkedIn: {exc}[/red bold]")
        sys.exit(1)

    scraper = LinkedInScraper(li_at, jsessionid, rate_limiter)

    already_collected: set[str] = set()
    if args.resume:
        already_collected = get_collected_job_ids(conn)
        console.print(f"[dim]Resume: {len(already_collected)} jobs já coletados no banco.[/dim]")

    console.print(Panel("[bold blue]Coletando vagas do LinkedIn...[/bold blue]"))

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  console=console) as progress:
        task = progress.add_task("Buscando vagas...", total=max_jobs)
        all_jobs: list[JobResult] = []

        if args.resume:
            stored = get_all_jobs(conn)
            all_jobs = list(stored)
            progress.update(task, completed=len(all_jobs))

        for qc in queries_cfg:
            current_count = len(all_jobs)
            if current_count >= max_jobs:
                break

            console.print(f"\n  [dim]Query: {qc['query']} (location={qc.get('location', '')})[/dim]")

            search_results = scraper.search_jobs(
                queries_config=[qc],
                max_jobs=max_jobs - current_count,
                listed_at=listed_at,
                skip_closed=args.skip_closed,
            )

            for j in search_results:
                if j.job_id in already_collected:
                    continue
                all_jobs.append(j)
                upsert_job(conn, j)
                progress.update(task, advance=1)

    new_jobs = [j for j in all_jobs if j.job_id not in already_collected]
    console.print(f"\n[green]{len(new_jobs)} novas vagas coletadas.[/green]\n")

    if args.scrape_only:
        console.print("[yellow]Modo scrape-only: análise LLM pulada.[/yellow]")
        display_from_db(conn, job_filter)
        return

    # ── LLM Analysis ──
    to_analyze: list[JobResult] = []
    if args.resume:
        analyzed_ids = get_analyzed_job_ids(conn)
        to_analyze = [j for j in all_jobs if j.job_id not in analyzed_ids]
        console.print(f"[dim]Resume: {len(to_analyze)} vagas pendentes de análise.[/dim]")
    else:
        to_analyze = new_jobs

    if to_analyze:
        llm = LLMClient(
            api_key=llm_api_key,
            model=llm_model,
            max_tokens=llm_cfg.get("max_tokens", 1024),
            temperature=llm_cfg.get("temperature", 0.3),
            timeout=llm_cfg.get("timeout", 30),
        )
        analyzer = JobAnalyzer(llm, profile_text, rate_limiter)
        analyze_and_store(analyzer, to_analyze, conn)
    else:
        console.print("[green]Todas as vagas já foram analisadas.[/green]")

    display_from_db(conn, job_filter)
    conn.close()


def analyze_and_store(
    analyzer: JobAnalyzer,
    jobs: list[JobResult],
    conn,
) -> None:
    """Executa análise em batch, salvando cada resultado no DB imediatamente."""
    saved_count = 0
    for job in tqdm(jobs, desc="Analisando vagas", unit="job"):
        job = analyzer.analyze(job)
        if job.score is not None:
            upsert_job(conn, job)
            conn.commit()
            saved_count += 1
            logger.info("  Score %d/10 — %s @ %s", job.score, job.title, job.company)
        else:
            logger.warning("  Falha na análise — %s @ %s", job.title, job.company)

        analyzer._limiter.wait()

        if analyzer._limiter.after_n_jobs():
            logger.info("  Aguardando cooldown longo...")
            analyzer._limiter.wait_cooldown()

    console.print(f"\n[green]{saved_count} vagas analisadas e salvas.[/green]")


def display_from_db(conn, job_filter: JobFilter) -> None:
    """Mostra tabela rich de resultados e painel de detalhes top 5."""
    jobs = get_filtered_jobs(conn, job_filter)

    # Filtros ativos resumidos para exibição
    active = []
    if job_filter.min_score:
        active.append(f"score≥{job_filter.min_score}")
    if job_filter.country != "all":
        active.append(job_filter.country)
    if job_filter.work_type != "all":
        active.append(job_filter.work_type)
    if job_filter.has_salary:
        active.append("com salário")
    if job_filter.min_salary:
        active.append(f"sal≥{job_filter.min_salary}")
    if job_filter.currency:
        active.append(job_filter.currency)
    if job_filter.easy_apply:
        active.append("easy-apply")
    if job_filter.company:
        active.append(f"empresa~{job_filter.company}")
    filter_str = "  [dim]Filtros: " + " | ".join(active) + "[/dim]" if active else ""

    if not jobs:
        console.print(f"\n[yellow]Nenhuma vaga encontrada com os filtros aplicados.[/yellow]{filter_str}")
        return

    console.print(f"\n[bold]{len(jobs)} vagas encontradas[/bold]{filter_str}\n")

    table = Table(
        title="Vagas com Melhor Match",
        box=box.ROUNDED,
        show_lines=True,
        header_style="bold cyan",
    )
    table.add_column("Score", width=7, justify="center")
    table.add_column("Vaga", min_width=28)
    table.add_column("Empresa", min_width=18)
    table.add_column("País", width=14)
    table.add_column("Tipo", width=9)
    table.add_column("Salário", width=14)
    table.add_column("Easy?", width=6, justify="center")
    table.add_column("Skills OK", min_width=18)
    table.add_column("Seniority", width=10)

    for job in jobs:
        color = score_color(job.score)
        salary_str = ""
        if job.has_salary and job.salary_min:
            top = f"–{job.salary_max}" if job.salary_max else ""
            salary_str = f"{job.salary_currency} {job.salary_min}{top}"
        table.add_row(
            Text(f"{job.score}/10" if job.score is not None else "—", style=f"bold {color}"),
            f"[link={job.link}]{job.title}[/link]",
            job.company or "—",
            job.country or job.location or "—",
            job.work_type or "—",
            salary_str or "—",
            "✓" if job.is_easy_apply else "",
            ", ".join(job.matched_skills[:4]) or "—",
            job.seniority_match or "—",
        )

    console.print(table)

    # Detalhes top 5
    console.print("\n[bold cyan]── Detalhes Top 5 ──[/bold cyan]\n")
    for job in jobs[:5]:
        color = score_color(job.score)
        salary_line = ""
        if job.has_salary:
            parts = []
            if job.salary_min:
                parts.append(str(job.salary_min))
            if job.salary_max:
                parts.append(str(job.salary_max))
            if parts:
                salary_line = f"\n💰 Salário: {job.salary_currency} " + " – ".join(parts)

        badges = []
        if job.work_type:
            badges.append(job.work_type)
        if job.is_easy_apply:
            badges.append("Easy Apply")
        if job.country:
            badges.append(job.country)
        badge_line = "  ".join(f"[dim]{b}[/dim]" for b in badges)

        console.print(Panel(
            f"[bold]{job.title}[/bold] @ {job.company or '?'}\n"
            f"{badge_line}{salary_line}\n\n"
            f"[{color}]Score: {job.score}/10[/{color}]  |  Seniority: {job.seniority_match}\n\n"
            f"OK: [green]{', '.join(job.matched_skills) or '—'}[/green]\n"
            f"Falta: [red]{', '.join(job.missing_skills) or 'nenhuma lacuna crítica'}[/red]\n\n"
            f"Resumo: {job.summary}\n\n"
            f"[link={job.link}]🔗 Ver vaga no LinkedIn[/link]",
            expand=False,
        ))


def score_color(score: int | None) -> str:
    if score is None:
        return "dim"
    if score >= 8:
        return "green"
    if score >= 6:
        return "yellow"
    return "red"


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # ── Carregar .env ──
    dotenv_path = BASE_DIR / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path)
        logger.debug("Carregado .env de %s", dotenv_path)

    # ── Carregar config ──
    cfg = load_config(BASE_DIR / args.config)
    profile_path = args.profile or (BASE_DIR / "my_profile.txt")
    profile_text = load_profile(profile_path)

    min_score = cfg["app"].get("min_score", 6)
    job_filter = build_job_filter(args, min_score)

    # ── Modo --show ──
    if args.show:
        conn = init_db(args.db)
        display_from_db(conn, job_filter)
        if args.export:
            export_csv(conn, args.export, job_filter)
            console.print(f"\n[dim]Exportado para [bold]{args.export}[/bold][/dim]")
        conn.close()
        return

    # ── Modo --export sozinho ──
    is_export_only = (
        args.export is not None
        and not args.scrape_only
        and not args.analyze_only
        and not args.resume
        and not args.show
    )
    if is_export_only:
        conn = init_db(args.db)
        display_from_db(conn, job_filter)
        export_csv(conn, args.export, job_filter)
        console.print(f"\n[dim]Exportado para [bold]{args.export}[/bold][/dim]")
        conn.close()
        return

    # ── Execução principal ──
    console.print(Panel(
        "[bold white]LinkedIn Job Matcher V2[/bold white]\n"
        "[dim]Busca vagas e avalia match com seu perfil usando IA via OpenRouter[/dim]",
        style="blue",
    ))

    run_full(
        cfg=cfg,
        profile_text=profile_text,
        db_path=args.db,
        args=args,
        env_path=dotenv_path,
    )


if __name__ == "__main__":
    main()
