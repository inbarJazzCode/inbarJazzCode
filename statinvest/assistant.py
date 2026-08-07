"""Optional LLM assistant that explains model results in plain language.

DESIGN NOTES — read before enabling.

This module talks to an **OpenAI-compatible** chat-completions endpoint. That
choice is deliberate: the same code works today against a paid API and later
against a free or local one, by changing only the base URL. Known-compatible
backends include OpenAI, OpenRouter, Groq, Together, LM Studio and Ollama
(``http://localhost:11434/v1``) — a local model costs nothing and never leaves
the machine.

SECURITY POSTURE
    * The API key is read from an environment variable **only**. It is never
      written to the database, never committed, never logged, and never shown
      in the UI or in exceptions.
    * The assistant is **off by default**. With no key configured, the entire
      application behaves exactly as before.
    * Enabling it means model summaries and ticker symbols are sent to a third
      party. That is a real departure from the app's local-first, no-telemetry
      posture, so it is opt-in, and :func:`describe_payload` shows the caller
      exactly what would be transmitted before anything is sent.
    * Only derived statistics are ever sent — coefficients, R², p-values,
      convergence flags. Never database contents, file paths, watchlists or
      anything identifying the user.
    * The model's output is treated as commentary, not as a computation. Every
      number in the app is produced by the estimators in
      :mod:`statinvest.models`; the assistant only puts them into words.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"

# Free / local alternatives, for when a no-cost backend is wanted. Each speaks
# the same OpenAI-compatible protocol, so only the base URL and model change.
FREE_BACKENDS = {
    "ollama (local, free)": ("http://localhost:11434/v1", "llama3.1"),
    "LM Studio (local, free)": ("http://localhost:1234/v1", "local-model"),
    "OpenRouter (free tier)": ("https://openrouter.ai/api/v1",
                               "meta-llama/llama-3.1-8b-instruct:free"),
    "OpenAI (paid)": (DEFAULT_BASE_URL, DEFAULT_MODEL),
}

SYSTEM_PROMPT = (
    "You explain the output of statistical models to someone doing investment "
    "research. Rules you must follow:\n"
    "1. Never invent numbers. Use only the figures given to you.\n"
    "2. Never give investment advice, price targets, or buy/sell suggestions.\n"
    "3. Say plainly when a result is weak: low R-squared, a p-value above 0.05, "
    "failure to converge, or out-of-sample performance near chance.\n"
    "4. Distinguish association from prediction, and prediction from profit.\n"
    "5. Be concise — at most two short paragraphs, plain language, no bullet lists.\n"
    "6. If the numbers do not support a conclusion, say so."
)


class AssistantError(RuntimeError):
    """Raised for assistant failures, with no sensitive detail attached."""


@dataclass
class AssistantConfig:
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    api_key_env: str = "STATINVEST_LLM_API_KEY"
    timeout: float = 30.0
    max_tokens: int = 400
    temperature: float = 0.2

    @property
    def api_key(self) -> str | None:
        """The key, read fresh from the environment. Never cached or stored."""
        key = os.environ.get(self.api_key_env)
        return key.strip() if key and key.strip() else None

    @property
    def enabled(self) -> bool:
        """Local backends need no key; remote ones do."""
        if self._is_local():
            return True
        return self.api_key is not None

    def _is_local(self) -> bool:
        u = self.base_url.lower()
        return "localhost" in u or "127.0.0.1" in u

    def status(self) -> dict:
        """Safe-to-display status. Never reveals the key itself."""
        return {
            "backend": self.base_url,
            "model": self.model,
            "local": self._is_local(),
            "key_env_var": self.api_key_env,
            "key_present": self.api_key is not None,
            "enabled": self.enabled,
        }


@dataclass
class Explanation:
    text: str
    model: str
    sent: dict = field(default_factory=dict)


def build_facts(spec: dict, result: dict, extra: dict | None = None) -> dict:
    """Assemble the *only* things that may be transmitted.

    An allow-list, not a filter: a field reaches the API only if it is named
    here, so new internal fields can never leak by default.
    """
    allowed_result = (
        "family", "n", "r_squared", "adj_r_squared", "se_type", "converged",
        "n_iter", "pseudo_r2_mcfadden", "dispersion", "deviance",
        "condition_number", "rank", "k", "warnings",
    )
    facts = {
        "specification": {k: spec.get(k) for k in
                          ("family", "target", "features", "formula",
                           "n_observations", "transformations") if k in spec},
        "result": {k: result[k] for k in allowed_result if k in result},
    }
    if "coefficients" in result:
        facts["coefficients"] = [
            {k: c.get(k) for k in ("term", "coef", "std_err", "p_value",
                                   "odds_ratio", "rate_ratio") if k in c}
            for c in result["coefficients"]
        ]
    if extra:
        facts["evaluation"] = {k: v for k, v in extra.items()
                               if isinstance(v, (int, float, str, bool, type(None)))}
    return facts


def describe_payload(facts: dict) -> str:
    """Exactly what would be sent, for the user to inspect before sending."""
    return json.dumps(facts, indent=2, default=str)


def explain(facts: dict, config: AssistantConfig | None = None,
            question: str | None = None) -> Explanation:
    """Ask the configured backend to describe ``facts`` in plain language.

    Raises :class:`AssistantError` with a non-sensitive message on any failure.
    The caller is expected to treat this as optional commentary.
    """
    cfg = config or AssistantConfig()
    if not cfg.enabled:
        raise AssistantError(
            f"No API key found. Set the {cfg.api_key_env} environment variable, "
            "or point the backend at a local model that needs no key."
        )

    user_msg = (
        "Explain these statistical results to a researcher.\n\n"
        f"{json.dumps(facts, default=str)}"
    )
    if question:
        user_msg += f"\n\nThe researcher asks: {question}"

    body = json.dumps({
        "model": cfg.model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "max_tokens": cfg.max_tokens,
        "temperature": cfg.temperature,
    }).encode()

    headers = {"Content-Type": "application/json"}
    key = cfg.api_key
    if key:
        headers["Authorization"] = f"Bearer {key}"

    req = urllib.request.Request(
        cfg.base_url.rstrip("/") + "/chat/completions", data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=cfg.timeout) as resp:
            doc = json.load(resp)
    except urllib.error.HTTPError as exc:
        # Status only — response bodies can echo the Authorization header.
        raise AssistantError(
            f"The language model backend returned HTTP {exc.code}. "
            "Check the model name and that the key is valid."
        ) from None
    except Exception as exc:
        raise AssistantError(
            f"Could not reach the language model backend ({type(exc).__name__}). "
            "If you are using a local model, make sure it is running."
        ) from None

    try:
        text = doc["choices"][0]["message"]["content"].strip()
    except Exception:
        raise AssistantError("The backend returned an unexpected response shape.") from None

    return Explanation(text=text, model=cfg.model, sent=facts)
