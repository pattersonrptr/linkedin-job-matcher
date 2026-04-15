"""
Sincronização do perfil LinkedIn com my_profile.txt.
Busca dados do perfil logado via linkedin-api e gera/atualiza
o arquivo de perfil usado na análise de vagas.
"""

import logging
from pathlib import Path

import requests
from linkedin_api import Linkedin

logger = logging.getLogger(__name__)


def _init_api(li_at: str, jsessionid: str) -> Linkedin:
    """Inicializa o cliente linkedin-api com cookies de sessão."""
    cookies = requests.cookies.RequestsCookieJar()
    cookies.set("li_at", li_at)
    cookies.set("JSESSIONID", jsessionid)
    return Linkedin(
        username="",
        password="",
        authenticate=True,
        cookies=cookies,
    )


def fetch_linkedin_profile(li_at: str, jsessionid: str) -> dict:
    """
    Busca dados completos do perfil logado no LinkedIn.
    Retorna dict com: profile, skills, experiences, contact_info.
    """
    api = _init_api(li_at, jsessionid)

    # Perfil do usuário logado
    user = api.get_user_profile(use_cache=False)
    public_id = user.get("miniProfile", {}).get("publicIdentifier", "")
    urn_id = user.get("miniProfile", {}).get("entityUrn", "").split(":")[-1]

    logger.info("Perfil encontrado: %s (urn: %s)", public_id, urn_id)

    # Perfil completo
    profile = api.get_profile(public_id=public_id) if public_id else {}

    # Skills
    skills = []
    try:
        skills = api.get_profile_skills(public_id=public_id) if public_id else []
    except Exception as exc:
        logger.warning("Erro ao buscar skills: %s", exc)

    # Experiências
    experiences = []
    try:
        if urn_id:
            experiences = api.get_profile_experiences(urn_id=urn_id)
    except Exception as exc:
        logger.warning("Erro ao buscar experiências: %s", exc)

    # Contato
    contact = {}
    try:
        contact = api.get_profile_contact_info(public_id=public_id) if public_id else {}
    except Exception as exc:
        logger.warning("Erro ao buscar contato: %s", exc)

    return {
        "user": user,
        "profile": profile,
        "skills": skills,
        "experiences": experiences,
        "contact": contact,
    }


def _format_experience(exp: dict) -> str:
    """Formata uma experiência do LinkedIn em texto legível."""
    company = exp.get("companyName", "?")
    title = exp.get("title", "?")

    # Período
    start = exp.get("timePeriod", {}).get("startDate", {})
    end = exp.get("timePeriod", {}).get("endDate", {})
    start_str = f"{start.get('month', '?')}/{start.get('year', '?')}" if start else "?"
    end_str = f"{end.get('month', '?')}/{end.get('year', '?')}" if end else "atual"

    desc = exp.get("description", "")
    line = f"- {company} ({start_str}–{end_str}): {title}"
    if desc:
        # Primeira linha da descrição, limitada
        short = desc.strip().split("\n")[0][:200]
        line += f". {short}"
    return line


def _format_education(edu: dict) -> str:
    """Formata uma educação do LinkedIn em texto."""
    school = edu.get("schoolName", "?")
    degree = edu.get("degreeName", "")
    field = edu.get("fieldOfStudy", "")
    start = edu.get("timePeriod", {}).get("startDate", {})
    end = edu.get("timePeriod", {}).get("endDate", {})
    start_str = str(start.get("year", "")) if start else ""
    end_str = str(end.get("year", "")) if end else ""
    period = f"({start_str}–{end_str})" if start_str or end_str else ""

    parts = [p for p in [degree, field] if p]
    desc = " em ".join(parts) if parts else ""
    return f"- {desc} — {school} {period}".strip()


def _format_certification(cert: dict) -> str:
    """Formata uma certificação do LinkedIn em texto."""
    name = cert.get("name", "?")
    authority = cert.get("authority", "")
    return f"- {name}" + (f" ({authority})" if authority else "")


def _format_course(course: dict) -> str:
    """Formata um curso do LinkedIn em texto."""
    name = course.get("name", "?")
    number = course.get("number", "")
    return f"- {name}" + (f" ({number})" if number else "")


def generate_profile_text(data: dict) -> str:
    """
    Gera o texto do my_profile.txt a partir dos dados do LinkedIn.
    Mantém seções compatíveis com o formato esperado pelo analyzer.
    """
    profile = data.get("profile", {})
    skills = data.get("skills", [])
    experiences = data.get("experiences", [])

    # ── Dados básicos ──
    first = profile.get("firstName", "")
    last = profile.get("lastName", "")
    name = f"{first} {last}".strip()
    headline = profile.get("headline", "")
    summary = profile.get("summary", "")
    location = profile.get("geoLocationName", "") or profile.get("locationName", "")
    country = profile.get("geoCountryName", "")
    location_full = f"{location}, {country}" if location and country else location or country

    # ── Línguas ──
    languages = profile.get("languages", [])
    lang_lines = []
    for lang in languages:
        lang_name = lang.get("name", "")
        proficiency = lang.get("proficiency", "")
        proficiency_map = {
            "NATIVE_OR_BILINGUAL": "nativo/bilíngue",
            "FULL_PROFESSIONAL": "fluente",
            "PROFESSIONAL_WORKING": "profissional",
            "LIMITED_WORKING": "intermediário",
            "ELEMENTARY": "básico",
        }
        level = proficiency_map.get(proficiency, proficiency)
        if lang_name:
            lang_lines.append(f"{lang_name} ({level})" if level else lang_name)

    # ── Skills ──
    skill_names = [s.get("name", "") for s in skills if s.get("name")]

    # ── Experiências ──
    exp_lines = [_format_experience(e) for e in experiences[:10]]

    # ── Educação ──
    education = profile.get("education", [])
    edu_lines = [_format_education(e) for e in education]

    # ── Certificações ──
    certifications = profile.get("certifications", [])
    cert_lines = [_format_certification(c) for c in certifications]

    # ── Cursos ──
    courses = profile.get("courses", [])
    course_lines = [_format_course(c) for c in courses]

    # ── Montar texto ──
    lines = []
    lines.append(f"Nome: {name}")
    if headline:
        lines.append(f"Cargo atual: {headline}")
    lines.append("")

    if summary:
        lines.append("Resumo:")
        lines.append(summary)
        lines.append("")

    if skill_names:
        lines.append("Skills do LinkedIn:")
        for chunk_start in range(0, len(skill_names), 8):
            chunk = skill_names[chunk_start:chunk_start + 8]
            lines.append("- " + ", ".join(chunk))
        lines.append("")

    if exp_lines:
        lines.append("Experiências (do LinkedIn):")
        lines.extend(exp_lines)
        lines.append("")

    if edu_lines:
        lines.append("Formação:")
        lines.extend(edu_lines)
        lines.append("")

    if certifications or courses:
        lines.append("Cursos e certificações (do LinkedIn):")
        lines.extend(cert_lines)
        lines.extend(course_lines)
        lines.append("")

    if lang_lines:
        lines.append("Idiomas: " + ", ".join(lang_lines))
        lines.append("")

    if location_full:
        lines.append(f"Localização: {location_full}")

    return "\n".join(lines)


def sync_profile(
    li_at: str,
    jsessionid: str,
    profile_path: Path,
    merge: bool = True,
) -> str:
    """
    Busca dados do perfil LinkedIn e gera/atualiza o arquivo de perfil.

    Args:
        merge: se True e o arquivo existir, adiciona seção 'Dados importados do LinkedIn'
               ao final. Se False, sobrescreve completamente.

    Retorna o texto gerado.
    """
    data = fetch_linkedin_profile(li_at, jsessionid)
    linkedin_text = generate_profile_text(data)

    if merge and profile_path.exists():
        existing = profile_path.read_text(encoding="utf-8")

        # Remover seção anterior de import se existir
        marker_start = "\n# ── Dados importados do LinkedIn ──\n"
        marker_end = "\n# ── Fim dos dados do LinkedIn ──\n"
        if marker_start in existing:
            before = existing[:existing.index(marker_start)]
            if marker_end in existing:
                after = existing[existing.index(marker_end) + len(marker_end):]
            else:
                after = ""
            existing = before.rstrip() + "\n" + after.lstrip()

        merged = (
            existing.rstrip() + "\n\n"
            + "# ── Dados importados do LinkedIn ──\n"
            + linkedin_text + "\n"
            + "# ── Fim dos dados do LinkedIn ──\n"
        )
        profile_path.write_text(merged, encoding="utf-8")
        logger.info("Perfil atualizado com dados do LinkedIn em %s", profile_path)
        return merged
    else:
        profile_path.write_text(linkedin_text, encoding="utf-8")
        logger.info("Perfil gerado a partir do LinkedIn em %s", profile_path)
        return linkedin_text
