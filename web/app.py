"""
LinkedIn Job Matcher V2 — Interface Web (Streamlit)
Execute com: streamlit run web/app.py
"""

import sys
import os
import time
import threading
from datetime import datetime
from pathlib import Path

# Adiciona o diretório raiz ao path para importar os módulos do projeto
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import streamlit as st
import pandas as pd
from dotenv import load_dotenv

from models import JobFilter, JobResult
from storage import export_csv, get_filtered_jobs, init_db, upsert_job

# ─────────────────────────────────────────────
# Configuração da página
# ─────────────────────────────────────────────

st.set_page_config(
    page_title="LinkedIn Job Matcher",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# Carregamento de ambiente
# ─────────────────────────────────────────────

_dotenv_path = ROOT / ".env"
if _dotenv_path.exists():
    load_dotenv(_dotenv_path)

DB_PATH = ROOT / "job_matcher.db"
CONFIG_PATH = ROOT / "config.toml"
PROFILE_PATH = ROOT / "my_profile.txt"


@st.cache_resource(show_spinner=False)
def get_db():
    """Retorna conexão persistente com o banco SQLite."""
    return init_db(DB_PATH)


def load_config():
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[import-not-found]
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


# ─────────────────────────────────────────────
# CSS customizado
# ─────────────────────────────────────────────

st.markdown("""
<style>
[data-testid="stSidebar"] { min-width: 280px; max-width: 340px; }
.job-card {
    border: 1px solid #333;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 12px;
    background: #1e1e1e;
}
.score-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-weight: bold;
    font-size: 1.1em;
}
.badge-green { background: #1a4731; color: #4ade80; }
.badge-yellow { background: #3d2e00; color: #facc15; }
.badge-red { background: #3d0f0f; color: #f87171; }
.badge-gray { background: #2a2a2a; color: #9ca3af; }
.chip {
    display: inline-block;
    padding: 1px 8px;
    border-radius: 8px;
    font-size: 0.78em;
    margin-right: 4px;
    background: #2a2a2a;
    color: #d1d5db;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def score_badge(score: int | None) -> str:
    if score is None:
        return '<span class="score-badge badge-gray">—</span>'
    cls = "badge-green" if score >= 8 else ("badge-yellow" if score >= 6 else "badge-red")
    return f'<span class="score-badge {cls}">{score}/10</span>'


def salary_str(job: JobResult) -> str:
    if not job.has_salary or not job.salary_min:
        return ""
    parts = [str(job.salary_min)]
    if job.salary_max:
        parts.append(str(job.salary_max))
    return f"{job.salary_currency} {' – '.join(parts)}"


def chip(text: str, color: str = "#2a2a2a") -> str:
    return f'<span class="chip" style="background:{color}">{text}</span>'


def render_job_card(job: JobResult) -> None:
    """Renderiza um card expandível de vaga."""
    title = job.title or "Sem título"
    company = job.company or "Empresa não informada"
    header = f"{score_badge(job.score)} **{title}** @ {company}"

    chips_html = ""
    if job.work_type:
        color = "#1a3a4f" if job.work_type == "remote" else ("#2f2a1a" if job.work_type == "hybrid" else "#1a2a1a")
        chips_html += chip(job.work_type, color)
    if job.country:
        chips_html += chip(job.country)
    if job.is_easy_apply:
        chips_html += chip("Easy Apply", "#1a3a1a")
    sal = salary_str(job)
    if sal:
        chips_html += chip(f"💰 {sal}", "#2a1a3a")

    with st.expander(f"{title}  ·  {company}  ·  score: {job.score or '—'}/10"):
        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown(f"#### {title}")
            st.markdown(f"🏢 **{company}**  |  📍 {job.location or job.country or '—'}")
            if chips_html:
                st.markdown(chips_html, unsafe_allow_html=True)
            st.markdown("")
            if job.summary:
                st.info(job.summary)
        with col2:
            st.markdown(f"**Score:** {score_badge(job.score)}", unsafe_allow_html=True)
            st.markdown(f"**Seniority:** {job.seniority_match or '—'}")
            if sal:
                st.markdown(f"**Salário:** {sal}")
            if job.link:
                st.link_button("🔗 Ver no LinkedIn", job.link)

        if job.matched_skills or job.missing_skills:
            c1, c2 = st.columns(2)
            with c1:
                st.success("**Skills compatíveis:**  \n" + (", ".join(job.matched_skills) or "—"))
            with c2:
                st.error("**Skills em falta:**  \n" + (", ".join(job.missing_skills) or "nenhuma lacuna crítica"))


# ─────────────────────────────────────────────
# Sidebar — Filtros
# ─────────────────────────────────────────────

def sidebar_filters(cfg: dict) -> JobFilter:
    st.sidebar.header("🔍 Filtros")

    min_score = st.sidebar.slider(
        "Score mínimo", 0, 10,
        value=cfg.get("app", {}).get("min_score", 6),
    )
    work_type = st.sidebar.selectbox(
        "Tipo de trabalho",
        ["all", "remote", "hybrid", "onsite"],
        format_func=lambda x: {"all": "Todos", "remote": "Remoto", "hybrid": "Híbrido", "onsite": "Presencial"}[x],
    )
    country = st.sidebar.selectbox(
        "Origem",
        ["all", "national", "international"],
        format_func=lambda x: {"all": "Todos", "national": "Brasil", "international": "Internacional"}[x],
    )
    easy_apply = st.sidebar.toggle("Apenas Easy Apply")
    has_salary = st.sidebar.toggle("Apenas com salário")

    min_salary = None
    currency = ""
    if has_salary:
        min_salary = st.sidebar.number_input("Salário mínimo", min_value=0, value=0, step=500) or None
        currency = st.sidebar.text_input("Moeda (USD, BRL…)", value="").upper()

    company = st.sidebar.text_input("Filtrar empresa", value="")
    sort = st.sidebar.radio(
        "Ordenar por",
        ["score", "date"],
        format_func=lambda x: "Score" if x == "score" else "Data de postagem",
    )

    return JobFilter(
        min_score=min_score,
        work_type=work_type,
        country=country,
        easy_apply=easy_apply,
        has_salary=has_salary,
        min_salary=min_salary if min_salary else None,
        currency=currency,
        company=company,
        sort=sort,
    )


# ─────────────────────────────────────────────
# Aba: Resultados
# ─────────────────────────────────────────────

def tab_results(job_filter: JobFilter) -> None:
    conn = get_db()
    jobs = get_filtered_jobs(conn, job_filter)

    if not jobs:
        st.warning("Nenhuma vaga encontrada com os filtros selecionados.")
        return

    # Métricas rápidas
    analyzed = [j for j in jobs if j.score is not None]
    avg_score = round(sum(j.score for j in analyzed) / len(analyzed), 1) if analyzed else 0
    top_jobs = [j for j in analyzed if j.score and j.score >= 8]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Vagas encontradas", len(jobs))
    m2.metric("Analisadas", len(analyzed))
    m3.metric("Score médio", avg_score)
    m4.metric("Score ≥ 8", len(top_jobs))

    st.divider()

    # Botão de exportação CSV
    col_exp, col_spacer = st.columns([1, 4])
    with col_exp:
        if st.button("📥 Exportar CSV"):
            tmp = ROOT / "_export_tmp.csv"
            export_csv(conn, tmp, job_filter)
            with open(tmp, "rb") as f:
                st.download_button(
                    "⬇️ Baixar CSV",
                    data=f,
                    file_name=f"vagas_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv",
                )
            tmp.unlink(missing_ok=True)

    # Cards de vagas
    for job in jobs:
        render_job_card(job)


# ─────────────────────────────────────────────
# Aba: Executar busca
# ─────────────────────────────────────────────

def tab_run_search(cfg: dict) -> None:
    st.header("🚀 Executar Busca")
    st.caption("Dispara o scraping e análise LLM diretamente pela interface.")

    with st.form("run_form"):
        col1, col2 = st.columns(2)
        with col1:
            max_jobs = st.number_input(
                "Máximo de vagas",
                min_value=1, max_value=200,
                value=cfg.get("scraper", {}).get("max_jobs", 30),
            )
            date_posted = st.selectbox(
                "Data de postagem",
                ["week", "24h", "month", "any"],
                format_func=lambda x: {"week": "Última semana", "24h": "Últimas 24h", "month": "Último mês", "any": "Qualquer"}[x],
            )
        with col2:
            skip_closed = st.toggle("Ignorar vagas fechadas", value=True)
            analyze = st.toggle("Analisar com LLM após coleta", value=True)

        submitted = st.form_submit_button("▶️ Iniciar busca", use_container_width=True)

    if submitted:
        _run_search_subprocess(max_jobs=max_jobs, date_posted=date_posted,
                               skip_closed=skip_closed, analyze=analyze)


def _run_search_subprocess(
    max_jobs: int,
    date_posted: str,
    skip_closed: bool,
    analyze: bool,
) -> None:
    """Executa main.py como subprocesso e exibe output em tempo real."""
    import subprocess

    st.info("Iniciando busca... Acompanhe o progresso abaixo.")
    output_area = st.empty()
    log_lines: list[str] = []

    cmd = [
        sys.executable, str(ROOT / "main.py"),
        "--max-jobs", str(max_jobs),
        "--date-posted", date_posted,
    ]
    if skip_closed:
        cmd.append("--skip-closed")
    else:
        cmd.append("--no-skip-closed")
    if analyze:
        cmd += []
    else:
        cmd.append("--scrape-only")

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(ROOT),
            env={**os.environ},
        )
        for line in proc.stdout:  # type: ignore[union-attr]
            # Limpar escape codes ANSI do rich
            clean = _strip_ansi(line.rstrip())
            if clean:
                log_lines.append(clean)
                output_area.code("\n".join(log_lines[-60:]), language="")
        proc.wait()
        if proc.returncode == 0:
            st.success("Busca concluída! Atualize a aba Resultados.")
            st.cache_resource.clear()
        else:
            st.error(f"Processo encerrou com código {proc.returncode}. Verifique o .env e configurações.")
    except Exception as exc:
        st.error(f"Erro ao executar busca: {exc}")


def _strip_ansi(text: str) -> str:
    """Remove escape codes ANSI de strings."""
    import re
    return re.sub(r"\x1b\[[0-9;]*[mK]|\x1b\[[0-9;]*[A-Z]", "", text)


# ─────────────────────────────────────────────
# Aba: Banco de dados
# ─────────────────────────────────────────────

def tab_database() -> None:
    st.header("🗄️ Banco de Dados")

    conn = get_db()
    from storage import get_all_jobs
    all_jobs = get_all_jobs(conn)

    if not all_jobs:
        st.info("Banco vazio. Execute uma busca primeiro.")
        return

    analyzed = [j for j in all_jobs if j.score is not None]
    pending = [j for j in all_jobs if j.score is None]
    easy_apply_count = sum(1 for j in all_jobs if j.is_easy_apply)
    remote_count = sum(1 for j in all_jobs if j.work_type == "remote")
    with_salary = sum(1 for j in all_jobs if j.has_salary)

    m1, m2, m3 = st.columns(3)
    m1.metric("Total de vagas", len(all_jobs))
    m2.metric("Analisadas", len(analyzed))
    m3.metric("Pendentes", len(pending))

    m4, m5, m6 = st.columns(3)
    m4.metric("Easy Apply", easy_apply_count)
    m5.metric("Remotas", remote_count)
    m6.metric("Com salário", with_salary)

    st.divider()

    # Tabela completa
    st.subheader("Todas as vagas")
    rows = []
    for j in all_jobs:
        rows.append({
            "Score": j.score,
            "Título": j.title,
            "Empresa": j.company,
            "País": j.country or j.location,
            "Tipo": j.work_type or "—",
            "Salário": salary_str(j) or "—",
            "Easy Apply": "✓" if j.is_easy_apply else "",
            "Seniority": j.seniority_match or "—",
            "Link": j.link,
        })
    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        column_config={
            "Score": st.column_config.NumberColumn(format="%d/10"),
            "Link": st.column_config.LinkColumn("Link"),
        },
        hide_index=True,
    )

    # Export completo
    st.divider()
    if st.button("📥 Exportar tudo para CSV"):
        tmp = ROOT / "_export_all.csv"
        export_csv(conn, tmp, None)
        with open(tmp, "rb") as f:
            st.download_button(
                "⬇️ Baixar CSV completo",
                data=f,
                file_name=f"vagas_completo_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
            )
        tmp.unlink(missing_ok=True)


# ─────────────────────────────────────────────
# Main layout
# ─────────────────────────────────────────────

def main() -> None:
    cfg = load_config()

    st.title("💼 LinkedIn Job Matcher")
    st.caption("Busca e análise de vagas com IA via OpenRouter")

    # Aviso se .env não configurado
    if not os.getenv("OPENROUTER_API_KEY"):
        st.warning("⚠️ OPENROUTER_API_KEY não definida no .env — análise LLM indisponível.")
    if not os.getenv("LI_AT"):
        st.warning("⚠️ LI_AT não definida no .env — scraping indisponível.")

    job_filter = sidebar_filters(cfg)

    tab1, tab2, tab3 = st.tabs(["📋 Resultados", "🚀 Executar Busca", "🗄️ Banco de Dados"])

    with tab1:
        tab_results(job_filter)

    with tab2:
        tab_run_search(cfg)

    with tab3:
        tab_database()


if __name__ == "__main__":
    main()
