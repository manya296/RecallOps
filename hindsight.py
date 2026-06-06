import os
import requests
from dotenv import load_dotenv

load_dotenv()

HINDSIGHT_API_KEY = os.getenv("HINDSIGHT_API_KEY")
HINDSIGHT_PIPELINE_ID = os.getenv("HINDSIGHT_PIPELINE_ID")
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
    bank_id = get_bank_id()
    url = f"{HINDSIGHT_API_URL}/v1/default/banks/{bank_id}/memories"

    content = (
        f"Service Affected: {incident_data.get('service_affected')}\n"
        f"Symptom Pattern: {incident_data.get('symptom_pattern')}\n"
        f"Root Cause: {incident_data.get('root_cause')}\n"
        f"Fix Applied: {incident_data.get('fix_applied')}\n"
        f"Time to Resolve: {incident_data.get('time_to_resolve_minutes')} minutes"
    )

    payload = {
        "items": [
            {
                "content": content,
                "metadata": incident_data
            }
        ]
    }

    response = requests.post(url, headers=get_headers(), json=payload)
    return response.status_code in (200, 201)

def recall_incidents(query: str, limit: int = 3) -> list:
    bank_id = get_bank_id()
    url = f"{HINDSIGHT_API_URL}/v1/default/banks/{bank_id}/memories/recall"

    payload = {
        "query": query,
        "limit": limit
    }

    response = requests.post(url, headers=get_headers(), json=payload)
    if response.status_code in (200, 201):
        data = response.json()
        raw_memories = data.get("memories") or data.get("items") or []

        parsed_incidents = []
        for mem in raw_memories:
            content_str = mem.get("content", "")
            relevance = mem.get("relevance_score", mem.get("score", 0.0))
            metadata = mem.get("metadata")

            parsed_incidents.append({
                "id": mem.get("id"),
                "content": content_str,
                "relevance_score": relevance,
                "structured": metadata if metadata else parse_retained_content(content_str)
            })
        return parsed_incidents
    else:
        response.raise_for_status()
        return []

def list_memories() -> list:
    bank_id = get_bank_id()
    url = f"{HINDSIGHT_API_URL}/v1/default/banks/{bank_id}/documents"

    response = requests.get(url, headers=get_headers())
    if response.status_code == 200:
        data = response.json()
        raw_memories = data.get("items") or data.get("memories") or []

        parsed_incidents = []
        for mem in raw_memories:
            content_str = (mem.get("original_text") or mem.get("content")
                           or mem.get("text") or mem.get("document") or "")
            metadata = mem.get("metadata")

            parsed_incidents.append({
                "id": mem.get("id"),
                "content": content_str,
                "structured": metadata if metadata else parse_retained_content(content_str)
            })
        return parsed_incidents
    else:
        response.raise_for_status()
        return []

def parse_retained_content(content_str: str) -> dict:
    lines = content_str.strip().split("\n")
    parsed = {}
    for line in lines:
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip().lower().replace(" ", "_")
            parsed[key] = val.strip()

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
