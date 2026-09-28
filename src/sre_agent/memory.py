"""Small local memory store for resolved incident summaries."""

import math
import re
from collections import Counter
from pathlib import Path

from sre_agent.models import IncidentState, MemoryHit

MEMORY_FILE = Path(__file__).parent / "data" / "incidents.md"
TOKEN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
RECORD = re.compile(
    r"(?ms)^# Incident (?P<incident_id>\S+)\s+"
    r"## Scope\s+(?P<scope>.*?)\s+"
    r"## Tenant\s+(?P<tenant>.*?)\s+"
    r"## Service\s+(?P<service>.*?)\s+"
    r"## Summary\s+(?P<summary>.*?)\s+"
    r"## Resolution\s+(?P<resolution>.*?)(?=^# Incident |\Z)"
)


def retrieve_incident_memory(
    tenant_id: str,
    service: str,
    query: str,
    top_k: int = 3,
    memory_file: Path = MEMORY_FILE,
) -> list[MemoryHit]:
    """Filter by tenant and service, then return the top TF-IDF matches."""
    records = []
    for record in _load_records(memory_file):
        scope = record["scope"].casefold()
        is_private_match = (
            scope == "private"
            and record["tenant"].casefold() == tenant_id.casefold()
            and record["service"].casefold() == service.casefold()
        )
        if scope == "global" or is_private_match:
            records.append(record)
    if not records or top_k < 1:
        return []

    documents = [_tokens(f"{item['summary']} {item['resolution']}") for item in records]
    document_frequency = Counter(term for tokens in documents for term in set(tokens))
    idf = {
        term: math.log((1 + len(documents)) / (1 + frequency)) + 1
        for term, frequency in document_frequency.items()
    }
    query_vector = _tfidf(_tokens(query), idf)

    ranked: list[tuple[float, dict[str, str]]] = []
    for record, tokens in zip(records, documents, strict=True):
        score = _cosine(query_vector, _tfidf(tokens, idf))
        if score > 0:
            ranked.append((score, record))
    ranked.sort(key=lambda item: (-item[0], item[1]["incident_id"]))

    return [
        MemoryHit(
            incident_id=record["incident_id"],
            scope=record["scope"],
            service=record["service"],
            summary=record["summary"],
            resolution=record["resolution"],
            score=round(score, 4),
        )
        for score, record in ranked[:top_k]
    ]


def retrieve_for_incident(state: IncidentState, top_k: int = 3) -> list[MemoryHit]:
    """Build a memory query from the current PagerDuty incident observation."""
    incident = next(
        (
            observation.payload
            for observation in state.observations
            if observation.tool == "pagerduty.get_incident" and observation.payload
        ),
        None,
    )
    if incident is None:
        return []
    service = str(incident.get("service", {}).get("summary", ""))
    title = str(incident.get("title", ""))
    if not service or not title:
        return []
    return retrieve_incident_memory(
        tenant_id=state.tenant_id,
        service=service,
        query=f"{service} {title}",
        top_k=top_k,
    )


def _load_records(path: Path) -> list[dict[str, str]]:
    text = path.read_text()
    return [
        {key: value.strip() for key, value in match.groupdict().items()}
        for match in RECORD.finditer(text)
    ]


def _tokens(text: str) -> list[str]:
    return TOKEN.findall(text.casefold())


def _tfidf(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    counts = Counter(token for token in tokens if token in idf)
    total = sum(counts.values())
    if not total:
        return {}
    return {term: count / total * idf[term] for term, count in counts.items()}


def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(value * right.get(term, 0.0) for term, value in left.items())
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    return dot / (left_norm * right_norm)
