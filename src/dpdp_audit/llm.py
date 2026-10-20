"""Thin LLM client with on-disk caching.

Backends:
  gemini  Google Gemini API (GEMINI_API_KEY, GEMINI_MODEL)
  openai  Any OpenAI-compatible server, e.g. vLLM serving Qwen2.5-7B-Instruct
          on Kaggle (OPENAI_BASE_URL, OPENAI_API_KEY, OPENAI_MODEL)

Every call is keyed by (backend, model, prompt, seed, temperature) and cached
under outputs/cache/llm/, so re-running an experiment costs nothing.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field

from dotenv import load_dotenv

from .paths import OUTPUTS, ROOT

load_dotenv(ROOT / ".env")
CACHE_DIR = OUTPUTS / "cache" / "llm"


@dataclass
class LLMResponse:
    text: str
    model: str
    seed: int
    # mean token probability of the answer, if the backend exposes log-probs
    token_prob: float | None = None
    usage: dict = field(default_factory=dict)
    cached: bool = False

    def json(self):
        return parse_json(self.text)


def parse_json(text: str):
    """Parse the first JSON object or array in a model reply."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = text.find(opener), text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"no JSON found in reply: {text[:200]!r}")


class LLM:
    def __init__(self, backend: str | None = None, model: str | None = None,
                 temperature: float = 0.7, max_tokens: int = 2048):
        self.backend = backend or os.getenv("LLM_BACKEND", "gemini")
        self.temperature = temperature
        self.max_tokens = max_tokens
        if self.backend == "gemini":
            self.model = model or os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
        elif self.backend == "openai":
            self.model = model or os.getenv("OPENAI_MODEL", "Qwen/Qwen2.5-7B-Instruct-AWQ")
        else:
            raise ValueError(f"unknown backend {self.backend}")
        self._client = None

    # ---------------------------------------------------------------- cache
    def _key(self, system: str, prompt: str, seed: int) -> str:
        blob = json.dumps([self.backend, self.model, system, prompt, seed, self.temperature])
        return hashlib.sha256(blob.encode()).hexdigest()

    def _cache_path(self, key: str):
        return CACHE_DIR / key[:2] / f"{key}.json"

    # ---------------------------------------------------------------- calls
    def complete(self, prompt: str, system: str = "", seed: int = 0) -> LLMResponse:
        key = self._key(system, prompt, seed)
        path = self._cache_path(key)
        if path.exists():
            data = json.loads(path.read_text())
            return LLMResponse(**data, cached=True)
        resp = self._call_with_retry(system, prompt, seed)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {k: v for k, v in resp.__dict__.items() if k != "cached"}
        path.write_text(json.dumps(payload))
        return resp

    def _call_with_retry(self, system, prompt, seed, attempts: int = 6) -> LLMResponse:
        delay = 5.0
        for i in range(attempts):
            try:
                if self.backend == "gemini":
                    return self._gemini(system, prompt, seed)
                return self._openai(system, prompt, seed)
            except Exception as exc:  # rate limits and transient server errors
                if i == attempts - 1:
                    raise
                msg = str(exc)
                wait = delay * (2 ** i)
                m = re.search(r"retry in ([\d.]+)s", msg)
                if m:
                    wait = float(m.group(1)) + 1
                time.sleep(min(wait, 120))
        raise RuntimeError("unreachable")

    def _gemini(self, system, prompt, seed) -> LLMResponse:
        from google import genai
        from google.genai import types

        if self._client is None:
            self._client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        config = types.GenerateContentConfig(
            system_instruction=system or None,
            temperature=self.temperature,
            max_output_tokens=self.max_tokens,
            seed=seed,
            response_mime_type="application/json",
        )
        r = self._client.models.generate_content(model=self.model, contents=prompt, config=config)
        usage = {}
        if r.usage_metadata:
            usage = {"prompt": r.usage_metadata.prompt_token_count,
                     "output": r.usage_metadata.candidates_token_count}
        return LLMResponse(text=r.text or "", model=self.model, seed=seed, usage=usage)

    def _openai(self, system, prompt, seed) -> LLMResponse:
        import math

        from openai import OpenAI

        if self._client is None:
            self._client = OpenAI(base_url=os.getenv("OPENAI_BASE_URL", "http://localhost:8000/v1"),
                                  api_key=os.getenv("OPENAI_API_KEY", "EMPTY"),
                                  timeout=float(os.getenv("OPENAI_TIMEOUT", "1800")))
        messages = ([{"role": "system", "content": system}] if system else []) + \
                   [{"role": "user", "content": prompt}]
        r = self._client.chat.completions.create(
            model=self.model, messages=messages, temperature=self.temperature,
            max_tokens=self.max_tokens, seed=seed, logprobs=True,
        )
        choice = r.choices[0]
        prob = None
        if choice.logprobs and choice.logprobs.content:
            lps = [t.logprob for t in choice.logprobs.content]
            prob = math.exp(sum(lps) / len(lps))
        usage = {"prompt": r.usage.prompt_tokens, "output": r.usage.completion_tokens} if r.usage else {}
        return LLMResponse(text=choice.message.content or "", model=self.model, seed=seed,
                           token_prob=prob, usage=usage)
