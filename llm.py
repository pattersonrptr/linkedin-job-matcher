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
