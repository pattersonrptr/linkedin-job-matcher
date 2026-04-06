"""
Utilidades anti-bloqueio para requisições ao LinkedIn.
Rotacao de User-Agent, delays aleatórios e cooldown periódico.
"""

import random
import time


# Pool de User-Agents recentes (Chrome, Firefox, Edge no Windows 10/11)
USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.7; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 OPR/116.0.0.0",
]


class UserAgentRotator:
    """Seleciona um User-Agent aleatório do pool a cada chamada."""

    def __init__(self, pool: list[str] | None = None) -> None:
        self._pool = pool or USER_AGENTS

    def get(self) -> str:
        """Retorna um User-Agent aleatório."""
        return random.choice(self._pool)


class RateLimiter:
    """Gerencia delays entre requisições com backoff exponencial e cooldown."""

    def __init__(
        self,
        delay_min: float = 2.0,
        delay_max: float = 5.0,
        cooldown_after: int = 10,
        cooldown_min: float = 30.0,
        cooldown_max: float = 120.0,
    ) -> None:
        self._delay_min = delay_min
        self._delay_max = delay_max
        self._cooldown_after = cooldown_after
        self._cooldown_min = cooldown_min
        self._cooldown_max = cooldown_max
        self._request_count = 0
        self._backoff_attempt = 0

    def get_delay(self) -> float:
        """Delay aleatório normal entre requisições."""
        return random.uniform(self._delay_min, self._delay_max)

    def on_rate_limit(self) -> float:
        """Calcula delay de backoff exponencial após 429/rate-limit."""
        self._backoff_attempt += 1
        base = max(self._delay_min, 2.0)
        delay = base * (2 ** self._backoff_attempt) + random.uniform(0.5, 2.0)
        return delay

    def reset_backoff(self) -> None:
        """Reseta o contador de backoff após sucesso."""
        self._backoff_attempt = 0

    def after_n_jobs(self) -> bool:
        """
        Retorna True se deve fazer cooldown após N jobs.
        Chamar após cada job processado. Reseta o contador internamente.
        """
        self._request_count += 1
        if self._request_count >= self._cooldown_after:
            self._request_count = 0
            return True
        return False

    def get_cooldown(self) -> float:
        """Duração do cooldown (pausa longa)."""
        return random.uniform(self._cooldown_min, self._cooldown_max)

    def wait(self) -> None:
        """Aguarda o delay normal entre requisições."""
        time.sleep(self.get_delay())

    def wait_cooldown(self) -> None:
        """Aguarda o período de cooldown longo."""
        duration = self.get_cooldown()
        time.sleep(duration)
