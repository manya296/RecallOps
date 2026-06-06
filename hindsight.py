import os
import requests
from dotenv import load_dotenv

load_dotenv()

HINDSIGHT_API_URL = os.getenv("HINDSIGHT_API_URL", "https://api.hindsight.vectorize.io")


def get_headers():
    api_key = os.getenv("HINDSIGHT_API_KEY")
    if not api_key:
        raise ValueError("HINDSIGHT_API_KEY is not set in environment variables.")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }


def get_bank_id():
    bank_id = os.getenv("HINDSIGHT_PIPELINE_ID")
    if not bank_id:
        raise ValueError("HINDSIGHT_PIPELINE_ID is not set in environment variables.")
    return bank_id


def retain_incident(incident_data: dict) -> bool:
    """
    Store an incident in Hindsight memory.
    Endpoint: POST /v1/default/banks/{bank_id}/memories
    Uses 'context' field to preserve structured metadata even after Hindsight rewrites content.
    """
    bank_id = get_bank_id()
    url = f"{HINDSIGHT_API_URL}/v1/default/banks/{bank_id}/memories"

    content = (
        f"Service Affected: {incident_data.get('service_affected')}. "
        f"Symptom Pattern: {incident_data.get('symptom_pattern')}. "
        f"Root Cause: {incident_data.get('root_cause')}. "
        f"Fix Applied: {incident_data.get('fix_applied')}. "
        f"Time to Resolve: {incident_data.get('time_to_resolve_minutes')} minutes."
    )

    # Store structured fields in context so they survive Hindsight's rewriting
    context = (
        f"service_affected={incident_data.get('service_affected')} | "
        f"symptom_pattern={incident_data.get('symptom_pattern')} | "
        f"root_cause={incident_data.get('root_cause')} | "
        f"fix_applied={incident_data.get('fix_applied')} | "
        f"time_to_resolve_minutes={incident_data.get('time_to_resolve_minutes', 0)}"
    )

    payload = {
        "items": [
            {
                "content": content,
                "context": context
            }
        ]
    }

    response = requests.post(url, headers=get_headers(), json=payload)

    if response.status_code not in (200, 201):
        print(f"[retain_incident] Failed: {response.status_code} - {response.text}")
        return False
    return True


def recall_incidents(query: str, limit: int = 3) -> list:
    """
    Retrieve relevant incidents from Hindsight memory.
    Endpoint: POST /v1/default/banks/{bank_id}/memories/recall
    """
    bank_id = get_bank_id()
    url = f"{HINDSIGHT_API_URL}/v1/default/banks/{bank_id}/memories/recall"

    payload = {
        "query": query,
        "limit": limit
    }

    response = requests.post(url, headers=get_headers(), json=payload)

    if response.status_code not in (200, 201):
        print(f"[recall_incidents] Failed: {response.status_code} - {response.text}")
        return []

    data = response.json()
    raw_memories = data.get("results") or []

    parsed_incidents = []
    for mem in raw_memories:
        content_str = mem.get("text", "")
        context_str = mem.get("context", "")
        relevance = mem.get("relevance_score", mem.get("score", 0.0))

        parsed_incidents.append({
            "id": mem.get("id"),
            "content": content_str,
            "relevance_score": relevance,
            "structured": parse_retained_content(content_str, context_str)
        })

    return parsed_incidents


def list_memories() -> list:
    """
    List all memories via a broad recall query.
    """
    bank_id = get_bank_id()
    url = f"{HINDSIGHT_API_URL}/v1/default/banks/{bank_id}/memories/recall"

    payload = {
        "query": "What service incidents have occurred? What were the root causes and fixes applied?",
        "limit": 50
    }

    response = requests.post(url, headers=get_headers(), json=payload)

    if response.status_code not in (200, 201):
        print(f"[list_memories] Failed: {response.status_code} - {response.text}")
        return []

    data = response.json()
    raw_memories = data.get("results") or []

    parsed_incidents = []
    for mem in raw_memories:
        content_str = mem.get("text", "")
        context_str = mem.get("context", "")
        parsed_incidents.append({
            "id": mem.get("id"),
            "content": content_str,
            "structured": parse_retained_content(content_str, context_str)
        })

    return parsed_incidents


def delete_all_memories() -> bool:
    """
    Delete all memories via the documents endpoint.
    """
    bank_id = get_bank_id()

    list_url = f"{HINDSIGHT_API_URL}/v1/default/banks/{bank_id}/documents"
    response = requests.get(list_url, headers=get_headers())

    if response.status_code != 200:
        print(f"[delete_all_memories] List failed: {response.status_code} - {response.text}")
        return False

    data = response.json()
    raw_memories = data.get("items") or data.get("memories") or []

    if not raw_memories:
        return True

    deleted = 0
    for mem in raw_memories:
        doc_id = mem.get("id")
        if not doc_id:
            continue
        del_url = f"{HINDSIGHT_API_URL}/v1/default/banks/{bank_id}/documents/{doc_id}"
        del_response = requests.delete(del_url, headers=get_headers())
        if del_response.status_code in (200, 204):
            deleted += 1

    if deleted == 0:
        bulk_url = f"{HINDSIGHT_API_URL}/v1/default/banks/{bank_id}/documents"
        bulk_response = requests.delete(bulk_url, headers=get_headers())
        return bulk_response.status_code in (200, 204)

    return True


def parse_retained_content(content_str: str, context_str: str = "") -> dict:
    """
    Parse a memory back into structured fields.

    Priority 1: Parse from context field (pipe-separated key=value pairs).
                 This is reliable since we wrote it ourselves.
    Priority 2: Parse from content_str (key: value lines).
    Priority 3: Extract service name from natural language via keyword matching.
    """

    # --- Priority 1: Parse from context field ---
    if context_str and "=" in context_str:
        parsed = {}
        parts = context_str.split("|")
        for part in parts:
            part = part.strip()
            if "=" in part:
                key, val = part.split("=", 1)
                parsed[key.strip()] = val.strip()

        if any(k in parsed for k in ["service_affected", "root_cause", "fix_applied"]):
            try:
                parsed["time_to_resolve_minutes"] = int(parsed.get("time_to_resolve_minutes", 0))
            except (ValueError, TypeError):
                parsed["time_to_resolve_minutes"] = 0
            parsed.setdefault("symptom_pattern", "N/A")
            parsed.setdefault("service_affected", "Unknown")
            parsed.setdefault("root_cause", "N/A")
            parsed.setdefault("fix_applied", "N/A")
            return parsed

    # --- Priority 2: Parse from content key: value lines ---
    normalized = content_str.replace(". ", "\n").strip()
    lines = normalized.split("\n")
    parsed = {}
    for line in lines:
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip().lower().replace(" ", "_")
            parsed[key] = val.strip().rstrip(".")

    if any(k in parsed for k in ["service_affected", "root_cause", "fix_applied"]):
        try:
            parsed["time_to_resolve_minutes"] = int(
                parsed.get("time_to_resolve", "0").replace("minutes", "").strip()
            )
        except (ValueError, TypeError):
            parsed["time_to_resolve_minutes"] = 0
        parsed.setdefault("symptom_pattern", "N/A")
        parsed.setdefault("service_affected", "Unknown")
        parsed.setdefault("root_cause", "N/A")
        parsed.setdefault("fix_applied", "N/A")
        return parsed

    # --- Priority 3: Natural language fallback — keyword extraction ---
    text = content_str.lower()
    service = "Unknown Service"
    for keyword in [
        "auth-service", "payment-service", "api-gateway", "redis",
        "database", "postgres", "frontend", "backend", "worker",
        "cache", "queue", "storage", "cdn", "load-balancer"
    ]:
        if keyword in text:
            service = keyword
            break

    return {
        "service_affected": service,
        "symptom_pattern": "N/A",
        "root_cause": content_str,
        "fix_applied": "N/A",
        "time_to_resolve_minutes": 0
    }
