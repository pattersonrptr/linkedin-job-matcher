"""
Gerenciamento automático de sessão LinkedIn.
Extrai cookies li_at e JSESSIONID via Chrome (undetected-chromedriver)
quando não estão disponíveis no ambiente, e persiste no .env.
"""

import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)

LINKEDIN_LOGIN_URL = "https://www.linkedin.com/login"
_POST_LOGIN_INDICATORS = ("/feed", "/mynetwork", "/jobs", "/messaging")


def fetch_cookies_via_browser(
    email: str,
    password: str,
    env_path: Path | None = None,
) -> tuple[str, str]:
    """
    Abre Chrome via undetected-chromedriver, realiza login no LinkedIn
    e retorna (li_at, jsessionid).
    Se env_path for fornecido, persiste os novos cookies no .env.
    """
    try:
        import undetected_chromedriver as uc
    except ImportError as exc:
        raise ImportError(
            "undetected-chromedriver não instalado. "
            "Execute: pip install undetected-chromedriver"
        ) from exc

    from dotenv import set_key

    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1200,800")

    logger.info("Abrindo Chrome para login automático no LinkedIn...")
    driver = uc.Chrome(options=options)

    try:
        driver.get(LINKEDIN_LOGIN_URL)
        time.sleep(2)

        # Preencher credenciais
        driver.find_element("id", "username").send_keys(email)
        pw_field = driver.find_element("id", "password")
        pw_field.send_keys(password)
        pw_field.submit()

        # Aguardar redirecionamento pós-login (max 60s)
        for _ in range(60):
            if any(ind in driver.current_url for ind in _POST_LOGIN_INDICATORS):
                break
            time.sleep(1)
        else:
            raise TimeoutError(
                "Login não completado em 60s. Verifique LINKEDIN_EMAIL e "
                "LINKEDIN_PASSWORD no .env."
            )

        # Extrair cookies relevantes
        browser_cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
        li_at = browser_cookies.get("li_at", "")
        jsessionid = browser_cookies.get("JSESSIONID", "")

        if not li_at or not jsessionid:
            raise ValueError(
                "Cookies li_at/JSESSIONID não encontrados após login. "
                "O login pode ter falhado silenciosamente."
            )

        logger.info("Cookies li_at e JSESSIONID extraídos com sucesso.")

        # Persistir no .env para reutilização futura
        if env_path and env_path.exists():
            set_key(str(env_path), "LI_AT", li_at)
            set_key(str(env_path), "JSESSIONID", jsessionid)
            logger.info("Cookies salvos em %s", env_path)

        # Atualizar o ambiente atual (uso imediato sem re-load do .env)
        os.environ["LI_AT"] = li_at
        os.environ["JSESSIONID"] = jsessionid

        return li_at, jsessionid

    finally:
        driver.quit()
        logger.info("Browser encerrado.")


def get_linkedin_cookies(
    env_path: Path | None = None,
) -> tuple[str, str]:
    """
    Retorna (li_at, jsessionid).

    Fluxo:
    1. Se LI_AT e JSESSIONID já estiverem no ambiente → usa diretamente.
    2. Caso contrário → abre Chrome, faz login com LINKEDIN_EMAIL / LINKEDIN_PASSWORD,
       extrai e salva os cookies no .env.

    Levanta EnvironmentError se os cookies não estiverem definidos e as
    credenciais de login também estiverem ausentes.
    """
    li_at = os.getenv("LI_AT", "")
    jsessionid = os.getenv("JSESSIONID", "")

    if li_at and jsessionid:
        return li_at, jsessionid

    # Fallback: login automático via browser
    email = os.getenv("LINKEDIN_EMAIL", "")
    password = os.getenv("LINKEDIN_PASSWORD", "")

    if not email or not password:
        raise EnvironmentError(
            "LI_AT/JSESSIONID ausentes e LINKEDIN_EMAIL/LINKEDIN_PASSWORD não definidos.\n"
            "Adicione suas credenciais ao .env para habilitar o login automático."
        )

    return fetch_cookies_via_browser(email, password, env_path)
