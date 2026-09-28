"""Local orchestrator on Apple Silicon via MLX. One model, no sub-agents."""

import json
import os
from typing import Any

from pydantic import ValidationError

from sre_agent.models import Decision, IncidentState
from sre_agent.prompt import system_prompt, user_message

DEFAULT_MODEL = "mlx-community/Qwen3-8B-4bit"


class HuggingFaceReasoner:
    def __init__(self, model_id: str | None = None, thinking: bool = False) -> None:
        self.model_id = model_id or os.environ.get("SRE_MODEL", DEFAULT_MODEL)
        self.thinking = thinking
        self._model: Any = None
        self._tokenizer: Any = None
        self.replies: list[str] = []

    def load(self) -> None:
        self._load_model()

    def __call__(self, state: IncidentState) -> Decision:
        from mlx_lm import generate
        from mlx_lm.sample_utils import make_sampler

        self._load_model()
        turn = user_message(state) if self.thinking else f"{user_message(state)}\n/no_think"
        messages = [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": turn},
        ]
        prompt = self._tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
        # Qwen3 recommends sampling over greedy decoding, which can loop while thinking.
        sampler = make_sampler(temp=0.6, top_p=0.95, top_k=20)
        max_tokens = 4096 if self.thinking else 1024
        error = ""
        for _ in range(2):
            reply = generate(self._model, self._tokenizer, prompt, max_tokens=max_tokens, sampler=sampler)
            self.replies.append(reply)
            try:
                return parse_decision(reply)
            except ValueError as exc:
                error = str(exc)
        raise ValueError(f"model failed to return a valid decision: {error}")

    def _load_model(self) -> None:
        if self._model is not None:
            return
        from mlx_lm import load

        self._model, self._tokenizer = load(self.model_id)


def parse_decision(reply: str) -> Decision:
    if "<think>" in reply and "</think>" not in reply:
        raise ValueError("model ran out of tokens while reasoning")
    text = reply.split("</think>")[-1]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("model did not return JSON")
    try:
        return Decision.model_validate(json.loads(text[start : end + 1], strict=False))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"invalid decision: {exc}") from exc
