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
    Payload:  { "items": [{ "content": "..." }] }
    """
    bank_id = get_bank_id()
    url = f"{HINDSIGHT_API_URL}/v1/default/banks/{bank_id}/memories"

    # Use natural language content as recommended by the docs
    content = (
        f"Service Affected: {incident_data.get('service_affected')}. "
        f"Symptom Pattern: {incident_data.get('symptom_pattern')}. "
        f"Root Cause: {incident_data.get('root_cause')}. "
        f"Fix Applied: {incident_data.get('fix_applied')}. "
        f"Time to Resolve: {incident_data.get('time_to_resolve_minutes')} minutes."
    )

    payload = {
        "items": [
            {
                "content": content
                # Note: the official API does not support a "metadata" field on items
                # per the docs — only "content", "context", and "timestamp"
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
    Response fields: results[].text, results[].type, results[].id
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
    # Docs say response key is "results", not "memories" or "items"
    raw_memories = data.get("results") or []

    parsed_incidents = []
    for mem in raw_memories:
        # Docs use "text" not "content"
        content_str = mem.get("text", "")
        # Docs don't return a relevance_score field — using a default
        relevance = mem.get("relevance_score", mem.get("score", 0.0))

        parsed_incidents.append({
            "id": mem.get("id"),
            "content": content_str,
            "relevance_score": relevance,
            "structured": parse_retained_content(content_str)
        })

    return parsed_incidents


def list_memories() -> list:
    """
    List all memories by doing a broad recall query.
    There is no dedicated list endpoint in the Hindsight API,
    so we use recall with a general incident-related query.
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
        parsed_incidents.append({
            "id": mem.get("id"),
            "content": content_str,
            "structured": parse_retained_content(content_str)
        })

    return parsed_incidents


def delete_all_memories() -> bool:
    """
    Delete all memories. The Hindsight docs don't document a bulk delete endpoint,
    so this attempts individual deletion via the documents endpoint.
    If that fails it tries a bulk DELETE on the documents endpoint.
    """
    bank_id = get_bank_id()

    # First, get all stored documents
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
        # Fallback: try bulk delete
        bulk_url = f"{HINDSIGHT_API_URL}/v1/default/banks/{bank_id}/documents"
        bulk_response = requests.delete(bulk_url, headers=get_headers())
        return bulk_response.status_code in (200, 204)

    return True


def parse_retained_content(content_str: str) -> dict:
    """
    Parse a retained memory string back into a structured dict.
    Handles both '. ' separated (new format) and '\n' separated (old format).
    """
    # Normalize both formats
    normalized = content_str.replace(". ", "\n").strip()
    lines = normalized.split("\n")

    parsed = {}
    for line in lines:
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip().lower().replace(" ", "_")
            parsed[key] = val.strip().rstrip(".")

    required_keys = ["service_affected", "symptom_pattern", "root_cause", "fix_applied"]
    if not any(k in parsed for k in required_keys):
        return {
            "service_affected": "Legacy / Unstructured",
            "symptom_pattern": "N/A",
            "root_cause": content_str,
            "fix_applied": "N/A",
            "time_to_resolve_minutes": 0
        }

    if "time_to_resolve" in parsed:
        time_str = parsed["time_to_resolve"].replace("minutes", "").strip()
        try:
            parsed["time_to_resolve_minutes"] = int(time_str)
        except ValueError:
            parsed["time_to_resolve_minutes"] = 0

    parsed.setdefault("time_to_resolve_minutes", 0)
    return parsed
