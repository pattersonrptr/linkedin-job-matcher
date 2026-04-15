"""
Camada LLM para o LinkedIn Job Matcher V2.
Cliente OpenAI-compatível apontado para OpenRouter com retry e extração robusta de JSON.
"""

import json
import logging
import time

from openai import OpenAI

logger = logging.getLogger(__name__)


def extract_json(text: str) -> dict | None:
    """
    Extrai o bloco JSON mais externo de uma string.
    Procura primeiro e ultimo `{`/`}` e tenta json.loads.
    Retorna dict ou None se falhar.
    """
    first = text.find("{")
    if first == -1:
        return None
    last = text.rfind("}")
    if last == -1 or last <= first:
        return None

    candidate = text[first : last + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        # Tenta remover blocos de markdown em volta
        cleaned = candidate.strip()
        for prefix in ("```json", "```"):
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("Falha ao extrair JSON da resposta LLM: %s", text[:200])
            return None


class LLMClient:
    """Cliente LLM via OpenRouter usando a interface OpenAI."""

    def __init__(
        self,
        api_key: str,
        model: str = "qwen/qwen2.5-72b-instruct",
        max_tokens: int = 1024,
        temperature: float = 0.3,
        timeout: int = 30,
    ) -> None:
        self._client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            timeout=timeout,
        )
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._max_retries = 3

    def analyze_job(self, prompt: str) -> dict | None:
        """
        Envia o prompt e retorna o dict analisado.
        Faz retry com backoff exponencial em caso de erro.
        """
        last_error = None
        for attempt in range(self._max_retries):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=self._max_tokens,
                    temperature=self._temperature,
                )
                raw = response.choices[0].message.content
                if not raw:
                    logger.warning("Resposta vazia do LLM (tentativa %d)", attempt + 1)
                    continue

                data = extract_json(raw)
                if data is not None:
                    return data

                logger.warning(
                    "Não foi possível extrair JSON (tentativa %d). Resposta: %s",
                    attempt + 1,
                    raw[:300],
                )

            except Exception as exc:
                last_error = exc
                wait = min(2 ** (attempt + 1) + 1, 30)
                logger.warning(
                    "Erro LLM (tentativa %d/%d): %s. Aguardando %ds...",
                    attempt + 1,
                    self._max_retries,
                    exc,
                    wait,
                )
                time.sleep(wait)

        logger.error("Falha ao analisar job após %d tentativas. Ultimo erro: %s", self._max_retries, last_error)
        return None

    def generate_queries(self, profile_text: str, location: str = "Brazil") -> list[dict] | None:
        """
        Gera queries de busca LinkedIn a partir do perfil do candidato.
        Retorna lista de dicts no formato do config.toml [[queries]] ou None se falhar.
        """
        prompt = (
            "Você é um especialista em recrutamento técnico. Analise o perfil do "
            "candidato abaixo e gere entre 3 e 6 queries de busca otimizadas para "
            "encontrar vagas compatíveis no LinkedIn.\n\n"
            "Regras:\n"
            "- Foque nas skills profissionais (stack principal) do candidato\n"
            "- Cada query deve ter termos que aparecem em títulos de vagas reais\n"
            "- Varie entre os diferentes perfis do candidato (ex: backend, cloud, devops)\n"
            "- Use termos em inglês (LinkedIn busca global)\n"
            "- Não repita a mesma combinação de palavras\n\n"
            "Retorne APENAS um JSON válido:\n"
            "{\n"
            '  "queries": [\n'
            '    {"query": "termo de busca", "location": "' + location + '", '
            '"experience": ["4"], "job_type": ["F"], "remote": ["2", "3"]},\n'
            "    ...\n"
            "  ]\n"
            "}\n\n"
            f"## PERFIL DO CANDIDATO\n{profile_text}\n\n"
            "Retorne APENAS o JSON."
        )

        last_error = None
        for attempt in range(self._max_retries):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=self._max_tokens,
                    temperature=0.5,
                )
                raw = response.choices[0].message.content
                if not raw:
                    continue

                data = extract_json(raw)
                if data and "queries" in data and isinstance(data["queries"], list):
                    return data["queries"]

                logger.warning(
                    "Formato inesperado na geração de queries (tentativa %d): %s",
                    attempt + 1, raw[:300],
                )
            except Exception as exc:
                last_error = exc
                wait = min(2 ** (attempt + 1) + 1, 30)
                logger.warning(
                    "Erro ao gerar queries (tentativa %d/%d): %s. Aguardando %ds...",
                    attempt + 1, self._max_retries, exc, wait,
                )
                time.sleep(wait)

        logger.error("Falha ao gerar queries após %d tentativas. Ultimo erro: %s", self._max_retries, last_error)
        return None
