"""LLM providers for the DA decision-support MVP.

Providers
---------
openrouter   Dev-time cloud provider (OpenAI-compatible chat completions).
local_gguf   CPU llama.cpp path. EXCLUDED by default for any model in
             config providers.local_gguf.excluded_models: the Qwen3.8-27B
             GGUF in the HF cache is the model the agent authoring this
             code runs on, so using it as the model under test would be
             circular (the model would be grading itself). A genuine
             local gate should use a different model (e.g. Gemma-3-27B or
             Llama-3.1-8B GGUF).

Cost control
------------
Every OpenRouter call is metered (usage tokens x live per-token pricing,
fetched once and cached in .pricing-cache.json) and accumulated in
spend.json. Calls beyond config.cost_budget_usd are refused, so a run
can never drain the account.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent


def load_config() -> dict:
    return json.loads((HERE / "config.json").read_text())


def load_env() -> dict:
    env_file = HERE / (load_config()["providers"]["openrouter"]["env_file"])
    out = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


# ---------------------------------------------------------------- JSON ---

def extract_json(text: str):
    """Best-effort extraction of a JSON object from model output.

    Tries, in order: the whole string; ```fenced``` blocks; the longest
    balanced {...} span (scanning from the last '{' backwards for a
    parseable object, then the first).
    """
    text = (text or "").strip()
    candidates = [text]
    candidates += re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    # balanced-brace candidates, longest first
    starts = [i for i, c in enumerate(text) if c == "{"]
    for i in reversed(starts):
        depth = 0
        in_str = False
        esc = False
        for j in range(i, len(text)):
            c = text[j]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        candidates.append(text[i : j + 1])
                        break
    for cand in candidates:
        try:
            return json.loads(cand)
        except Exception:
            continue
    return None


# ---------------------------------------------------------------- costs ---

class CostLedger:
    def __init__(self, config: dict):
        self.file = HERE / "spend.json"
        self.budget = float(config.get("cost_budget_usd", 4.0))
        if self.file.exists():
            self.state = json.loads(self.file.read_text())
        else:
            self.state = {"total_usd": 0.0, "calls": 0, "per_call_usd": []}

    def charge(self, usd: float, model: str) -> None:
        self.state["total_usd"] = round(self.state["total_usd"] + usd, 6)
        self.state["calls"] += 1
        self.state["per_call_usd"].append(round(usd, 6))
        self.file.write_text(json.dumps(self.state, indent=1))

    def check(self, estimate_usd: float = 0.0) -> None:
        if self.state["total_usd"] + estimate_usd > self.budget:
            raise RuntimeError(
                f"cost budget exceeded: spent ${self.state['total_usd']:.4f}, "
                f"estimated ${estimate_usd:.4f}, budget ${self.budget:.2f}"
            )


def get_pricing(cfg: dict, model: str) -> dict:
    """Per-token USD pricing for an OpenRouter model (cached on disk)."""
    cache = HERE / ".pricing-cache.json"
    data = json.loads(cache.read_text()) if cache.exists() else {}
    if model in data:
        return data[model]
    env = load_env()
    r = requests.get(
        cfg["providers"]["openrouter"]["api_base"] + "/models",
        headers={"Authorization": f"Bearer {env['OPENROUTER_API_KEY']}"},
        timeout=30,
    )
    r.raise_for_status()
    for m in r.json()["data"]:
        if m["id"] == model:
            data[model] = m.get("pricing", {})
            break
    cache.write_text(json.dumps(data, indent=1))
    return data.get(model, {})


# ------------------------------------------------------------ providers ---

class OpenRouterLLM:
    provider = "openrouter"

    def __init__(self, config: dict, model: str | None = None):
        self.cfg = config
        self.model = model or config["providers"]["openrouter"]["default_model"]
        env = load_env()
        self.api_key = env.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENROUTER_API_KEY missing from "
                               + config["providers"]["openrouter"]["env_file"])
        self.base = config["providers"]["openrouter"]["api_base"]
        self.pricing = get_pricing(config, self.model)
        self.ledger = CostLedger(config)

    def chat(self, messages, max_tokens=4096, temperature=None) -> dict:
        """One chat completion. Returns {content, model, in_tokens,
        out_tokens, usd, ms, attempts}."""
        temperature = (self.cfg.get("temperature", 0.0) if temperature is None
                       else temperature)
        est = 0.0
        last_err = None
        for attempt in range(1, self.cfg.get("max_retries", 2) + 2):
            self.ledger.check(est)
            t0 = time.time()
            try:
                r = requests.post(
                    self.base + "/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                    },
                    timeout=600,
                )
            except requests.RequestException as e:  # network blip
                last_err = f"network: {e}"
                time.sleep(3 * attempt)
                continue
            if r.status_code != 200:
                last_err = f"HTTP {r.status_code}: {r.text[:300]}"
                time.sleep(3 * attempt)
                continue
            body = r.json()
            usage = body.get("usage", {})
            content = body["choices"][0]["message"]["content"]
            usd = (usage.get("prompt_tokens", 0)
                   * float(self.pricing.get("prompt", 0))
                   + usage.get("completion_tokens", 0)
                   * float(self.pricing.get("completion", 0)))
            self.ledger.charge(usd, self.model)
            return {
                "content": content,
                "model": self.model,
                "in_tokens": usage.get("prompt_tokens", 0),
                "out_tokens": usage.get("completion_tokens", 0),
                "usd": usd,
                "ms": round((time.time() - t0) * 1000),
                "attempts": attempt,
                "error": None,
            }
        return {"content": None, "model": self.model, "error": last_err,
                "attempts": self.cfg.get("max_retries", 2) + 1, "usd": 0.0,
                "in_tokens": 0, "out_tokens": 0, "ms": 0}

    def chat_json(self, messages, max_tokens=4096, hint: str = "the JSON object"):
        """Chat completion that must return a JSON object; retries with a
        corrective reminder if parsing fails."""
        msgs = list(messages)
        result = None
        for attempt in range(1, self.cfg.get("max_retries", 2) + 1):
            result = self.chat(msgs, max_tokens=max_tokens)
            if result["error"]:
                continue
            obj = extract_json(result["content"])
            if obj is not None:
                result["json"] = obj
                return result
            msgs = messages + [
                {"role": "assistant", "content": result["content"]},
                {"role": "user",
                 "content": "Your previous reply could not be parsed as JSON. "
                            f"Reply again with ONLY the valid {hint}, "
                            "no prose, no markdown."},
            ]
        if result and result.get("content"):
            result["json"] = extract_json(result["content"])
        return result


class LocalGGUFLLM:
    provider = "local_gguf"

    def __init__(self, config: dict, model_path: str):
        self.cfg = config
        cfg = config["providers"]["local_gguf"]
        name = Path(model_path).name
        for excluded in cfg.get("excluded_models", []):
            if excluded.lower() in name.lower():
                raise RuntimeError(
                    f"refusing to use {name} as the model under test: it "
                    f"matches excluded model '{excluded}' — that GGUF is the "
                    "model the authoring agent runs on (circular). Choose a "
                    "different local model."
                )
        import llama_cpp  # lazy: only needed for local runs

        self.llm = llama_cpp.Llama(
            model_path=model_path,
            n_ctx=int(cfg.get("n_ctx", 16384)),
            n_batch=512,
            n_threads=int(cfg.get("n_threads", 16)),
            verbose=False,
        )

    def chat(self, messages, max_tokens=4096, temperature=None) -> dict:
        temperature = (self.cfg.get("temperature", 0.0) if temperature is None
                       else temperature)
        fmt = self.llm._create_chat_format(messages)
        t0 = time.time()
        out = self.llm.create_completion(
            prompt=fmt, max_tokens=max_tokens, temperature=temperature
        )
        content = out["choices"][0]["text"]
        n = out.get("usage", {}).get("completion_tokens", 0)
        return {"content": content, "model": Path(self.llm.model_path).name,
                "in_tokens": 0, "out_tokens": n, "usd": 0.0,
                "ms": round((time.time() - t0) * 1000), "attempts": 1,
                "error": None}

    def chat_json(self, messages, max_tokens=4096, hint: str = "the JSON object"):
        result = self.chat(messages, max_tokens=max_tokens)
        if result["content"] is not None:
            result["json"] = extract_json(result["content"])
        return result


def get_llm(config: dict | None = None, model: str | None = None):
    config = config or load_config()
    if model and ":" in model:
        provider, name = model.split(":", 1)
        if provider == "local_gguf":
            return LocalGGUFLLM(config, name)
    return OpenRouterLLM(config, model)
