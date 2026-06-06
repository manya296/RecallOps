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

def delete_all_memories() -> bool:
    bank_id = get_bank_id()
    url = f"{HINDSIGHT_API_URL}/v1/default/banks/{bank_id}/documents"
    response = requests.get(url, headers=get_headers())
    if response.status_code != 200:
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

            parsed_incidents.append({
                "id": mem.get("id"),
                "content": content_str,
                "relevance_score": relevance,
                "structured": parse_retained_content(content_str)
            })
