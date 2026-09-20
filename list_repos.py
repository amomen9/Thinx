#!/usr/bin/env python3
"""
List all repositories in AllegroGraph
"""

import os
import requests
from requests.auth import HTTPBasicAuth

# Finding H1: this file used to carry a hosted AllegroGraph endpoint and a live
# password. Everything now comes from the environment, and the script refuses to
# run rather than falling back to a default credential.
AGRAPH_HOST = os.getenv("AGRAPH_HOST", "localhost")
AGRAPH_PORT = int(os.getenv("AGRAPH_PORT", 10035))
AGRAPH_USER = os.getenv("AGRAPH_USER", "admin")
AGRAPH_PASSWORD = os.getenv("AGRAPH_PASSWORD")
if not AGRAPH_PASSWORD:
    raise SystemExit("AGRAPH_PASSWORD is not set. Export it before running this script.")

BASE_URL = f"http://{AGRAPH_HOST}:{AGRAPH_PORT}"

def list_repositories():
    """List all repositories in all catalogs"""
    
    # Get root catalog repositories
    url = f"{BASE_URL}/repositories"
    
    try:
        response = requests.get(
            url,
            auth=HTTPBasicAuth(AGRAPH_USER, AGRAPH_PASSWORD),
            headers={"Accept": "application/json"}
        )
        response.raise_for_status()
        
        data = response.json()
        print("Repositories found in AllegroGraph:")
        print("=" * 60)
        
        if isinstance(data, list):
            for repo in data:
                repo_id = repo.get("id", "Unknown")
                repo_title = repo.get("title", "No title")
                print(f"  - {repo_id} ({repo_title})")
        else:
            print(data)
            
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"Error listing repositories: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"Response: {e.response.text}")
        return []

if __name__ == "__main__":
    list_repositories()
