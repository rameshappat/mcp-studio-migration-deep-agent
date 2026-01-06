#!/usr/bin/env python3
"""Clear LangSmith traces for a project.

This script deletes traces from a LangSmith project using the LangSmith API.
By default it performs a dry-run; pass --yes to actually delete.

Required env var:
- LANGSMITH_API_KEY

Optional env vars:
- LANGSMITH_PROJECT (defaults to "default")

Example:
  export LANGSMITH_API_KEY="lsv2_pt_..."
  python scripts/clear_langsmith_traces.py --yes
  python scripts/clear_langsmith_traces.py --project my-project --yes
  python scripts/clear_langsmith_traces.py --limit 100 --yes  # Delete only 100 traces
"""

from __future__ import annotations

import argparse
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")
except Exception:
    pass


LANGSMITH_API_BASE = "https://api.smith.langchain.com/api/v1"


def _get_api_key() -> str:
    return (os.environ.get("LANGSMITH_API_KEY") or "").strip()


def _get_default_project() -> str:
    return (os.environ.get("LANGSMITH_PROJECT") or "default").strip()


def _auth_headers(api_key: str) -> dict[str, str]:
    return {
        "x-api-key": api_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def list_sessions(client: httpx.Client, max_retries: int = 5) -> list[dict]:
    """List all projects/sessions in LangSmith."""
    for attempt in range(max_retries):
        resp = client.get(f"{LANGSMITH_API_BASE}/sessions")
        
        if resp.status_code == 429:
            wait_time = min(5 * (attempt + 1), 60)
            print(f"Rate limited listing sessions, waiting {wait_time}s...")
            time.sleep(wait_time)
            continue
            
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise RuntimeError(f"Failed to list sessions ({resp.status_code}): {detail}")
        
        return resp.json() or []
    
    raise RuntimeError("Max retries exceeded due to rate limiting")


def get_session_id(client: httpx.Client, project_name: str) -> str | None:
    """Get the session ID for a project name."""
    sessions = list_sessions(client)
    for session in sessions:
        if session.get("name") == project_name:
            return session.get("id")
    return None


def list_traces(
    client: httpx.Client,
    session_id: str,
    limit: int = 100,
    offset: int = 0,
    max_retries: int = 5,
) -> list[dict]:
    """List traces (runs) for a session with retry logic for rate limits."""
    # LangSmith uses POST for querying runs with filters
    payload = {
        "session": [session_id],  # API expects a list of session IDs
        "limit": min(limit, 100),  # API max is 100 per request
        "offset": offset,
        "is_root": True,  # Only get root traces
    }
    
    for attempt in range(max_retries):
        resp = client.post(f"{LANGSMITH_API_BASE}/runs/query", json=payload)
        
        if resp.status_code == 429:
            # Rate limited - wait and retry with exponential backoff
            wait_time = min(5 * (attempt + 1), 60)  # 5, 10, 15, 20, 25 seconds
            print(f"  Rate limited, waiting {wait_time}s...")
            time.sleep(wait_time)
            continue
            
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise RuntimeError(f"Failed to list traces ({resp.status_code}): {detail}")
        
        data = resp.json()
        # API may return {"runs": [...]} or just [...]
        if isinstance(data, dict) and "runs" in data:
            return data["runs"]
        return data or []
    
    raise RuntimeError("Max retries exceeded due to rate limiting")


def delete_traces(
    client: httpx.Client,
    trace_ids: list[str],
    session_id: str,
    max_retries: int = 3,
) -> dict:
    """Delete traces by IDs (up to 1000 per request) with retry logic."""
    if not trace_ids:
        return {"deleted": 0}
    
    # API supports up to 1000 trace IDs per request
    batch_size = 1000
    total_deleted = 0
    
    for i in range(0, len(trace_ids), batch_size):
        batch = trace_ids[i:i + batch_size]
        payload = {
            "trace_ids": batch,
            "session_id": session_id,
        }
        
        for attempt in range(max_retries):
            resp = client.post(f"{LANGSMITH_API_BASE}/runs/delete", json=payload)
            
            if resp.status_code == 429:
                wait_time = 2 ** attempt
                print(f"  Rate limited during delete, waiting {wait_time}s...")
                time.sleep(wait_time)
                continue
                
            if resp.status_code >= 400:
                try:
                    detail = resp.json()
                except Exception:
                    detail = resp.text
                print(f"Warning: Failed to delete batch ({resp.status_code}): {detail}")
            else:
                total_deleted += len(batch)
            break
    
    return {"deleted": total_deleted}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clear LangSmith traces for a project"
    )
    parser.add_argument(
        "--project",
        type=str,
        default=None,
        help="LangSmith project name (defaults to LANGSMITH_PROJECT env or 'default')",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of traces to delete (default: all)",
    )
    parser.add_argument(
        "--older-than-days",
        type=int,
        default=None,
        help="Only delete traces older than N days",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Actually delete traces (otherwise dry-run)",
    )
    parser.add_argument(
        "--list-projects",
        action="store_true",
        help="List all available projects and exit",
    )
    args = parser.parse_args()

    api_key = _get_api_key()
    if not api_key:
        raise SystemExit(
            "Missing API key. Set LANGSMITH_API_KEY environment variable."
        )

    project_name = args.project or _get_default_project()

    with httpx.Client(headers=_auth_headers(api_key), timeout=60.0) as client:
        # List projects if requested
        if args.list_projects:
            print("Available LangSmith projects:")
            sessions = list_sessions(client)
            for session in sessions:
                name = session.get("name", "unknown")
                sid = session.get("id", "unknown")
                trace_count = session.get("run_count", "?")
                print(f"  - {name} (id: {sid}, traces: {trace_count})")
            return 0

        # Get session ID for project
        session_id = get_session_id(client, project_name)
        if not session_id:
            print(f"Project '{project_name}' not found.")
            print("\nAvailable projects:")
            sessions = list_sessions(client)
            for session in sessions:
                print(f"  - {session.get('name')}")
            return 1

        print(f"Project: {project_name} (session_id: {session_id})")

        # Collect all trace IDs
        all_trace_ids: list[str] = []
        offset = 0
        batch_limit = 100  # API max is 100 per request
        max_traces = args.limit or float("inf")
        
        # Calculate cutoff date if --older-than-days is specified
        cutoff_date = None
        if args.older_than_days is not None:
            cutoff_date = datetime.utcnow() - timedelta(days=args.older_than_days)
            print(f"Filtering traces older than {cutoff_date.isoformat()}Z")

        print("Fetching traces...")
        while len(all_trace_ids) < max_traces:
            traces = list_traces(client, session_id, limit=batch_limit, offset=offset)
            if not traces:
                break
            
            for trace in traces:
                if len(all_trace_ids) >= max_traces:
                    break
                
                trace_id = trace.get("trace_id") or trace.get("id")
                if not trace_id:
                    continue
                
                # Filter by date if specified
                if cutoff_date:
                    start_time_str = trace.get("start_time")
                    if start_time_str:
                        try:
                            # Parse ISO format datetime
                            start_time = datetime.fromisoformat(
                                start_time_str.replace("Z", "+00:00")
                            ).replace(tzinfo=None)
                            if start_time >= cutoff_date:
                                continue  # Skip traces newer than cutoff
                        except Exception:
                            pass  # Include if we can't parse the date
                
                all_trace_ids.append(trace_id)
            
            offset += batch_limit
            print(f"  Found {len(all_trace_ids)} traces so far...")
            
            # Add delay between requests to avoid rate limiting
            time.sleep(1.0)

        print(f"\nFound {len(all_trace_ids)} traces to delete.")

        if not all_trace_ids:
            print("Nothing to delete.")
            return 0

        if not args.yes:
            print("\nDry-run only. Re-run with --yes to delete.")
            print(f"First 10 trace IDs: {all_trace_ids[:10]}")
            return 0

        # Delete traces
        print(f"\nDeleting {len(all_trace_ids)} traces...")
        result = delete_traces(client, all_trace_ids, session_id)
        print(f"✅ Deleted {result['deleted']} traces.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
