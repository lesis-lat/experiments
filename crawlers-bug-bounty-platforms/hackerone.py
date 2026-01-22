import requests
import time
import json
from urllib.parse import urljoin

request_headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Origin": "https://hackerone.com",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "X-Requested-With": "XMLHttpRequest"
}

base_url = "https://hackerone.com"
programs_search_url = "https://hackerone.com/programs/search?query=bounties%3Ayes&sort=name%3Aascending&limit=1000"
graphql_url = "https://hackerone.com/graphql"

graphql_query = """
query TeamProfile($handle: String!) {
  team(handle: $handle) {
    id
    handle
    state
    url
    type
    external_program {
      id
      offers_rewards
      thanks_url
      __typename
    }
    organization {
      features {
        key
        __typename
      }
      __typename
    }
    declarative_policy {
      id
      protected_by_gold_standard_safe_harbor
      __typename
    }
    ...BountyTable
    __typename
  }
  me {
    id
    has_active_ban
    __typename
  }
}

fragment BountyTable on Team {
  id
  handle
  profile_metrics_snapshot {
    average_bounty_per_severity_low
    average_bounty_per_severity_medium
    average_bounty_per_severity_high
    average_bounty_per_severity_critical
    report_count_per_severity_low
    report_count_per_severity_medium
    report_count_per_severity_high
    report_count_per_severity_critical
    __typename
  }
  bounty_table {
    id
    low_label
    medium_label
    high_label
    critical_label
    description
    use_range
    bounty_table_rows(first: 100) {
      nodes {
        id
        low
        medium
        high
        critical
        low_minimum
        medium_minimum
        high_minimum
        critical_minimum
        smart_rewards_start_at
        structured_scope {
          id
          asset_identifier
          __typename
        }
        updated_at
        __typename
      }
      __typename
    }
    updated_at
    __typename
  }
  __typename
}
"""

def get_program_links():
    try:
        response = requests.get(programs_search_url, headers=request_headers)
        response.raise_for_status()
        print(f"HTTP Status: {response.status_code}, URL: {response.url}")
        
        data = response.json()
        programs = data.get("results", [])
        print(f"Found {len(programs)} programs")
        
        program_links = [
            {"url": urljoin(base_url, program_summary["url"]), "handle": program_summary["handle"]}
            for program_summary in programs
            if program_summary.get("url") and program_summary.get("handle")
        ]
        
        return program_links
    except requests.RequestException as request_error:
        print(f"Error fetching program list: {request_error}")
        return []
    except ValueError as parse_error:
        print(f"Error parsing JSON response for programs: {parse_error}")
        return []

def extract_rewards(program_url, handle):
    try:
        payload = {
            "operationName": "TeamProfile",
            "variables": {"handle": handle, "product_area": "team_profile", "product_feature": "overview"},
            "query": graphql_query
        }
        
        response = requests.post(graphql_url, headers=request_headers, json=payload)
        response.raise_for_status()
        
        data = response.json()
        team_data = data.get("data", {}).get("team", {})
        
        reward_data = {
            "program_url": program_url,
            "program_name": handle,
            "bounty_table": None,
            "offers_bounties": team_data.get("offers_bounties", False),
            "offers_thanks": team_data.get("offers_thanks", False)
        }
        
        bounty_table = team_data.get("bounty_table")
        if bounty_table:
            reward_data["bounty_table"] = {
                "id": bounty_table.get("id"),
                "description": bounty_table.get("description"),
                "use_range": bounty_table.get("use_range"),
                "rewards": []
            }
            bounty_rows = bounty_table.get("bounty_table_rows", {}).get("nodes", [])
            for row in bounty_rows:
                reward_entry = {
                    "low_label": bounty_table.get("low_label"),
                    "low": row.get("low"),
                    "low_minimum": row.get("low_minimum"),
                    "medium_label": bounty_table.get("medium_label"),
                    "medium": row.get("medium"),
                    "medium_minimum": row.get("medium_minimum"),
                    "high_label": bounty_table.get("high_label"),
                    "high": row.get("high"),
                    "high_minimum": row.get("high_minimum"),
                    "critical_label": bounty_table.get("critical_label"),
                    "critical": row.get("critical"),
                    "critical_minimum": row.get("critical_minimum"),
                    "updated_at": row.get("updated_at")
                }
                reward_data["bounty_table"]["rewards"].append(reward_entry)
        
        return reward_data
    except requests.RequestException as request_error:
        print(f"Error fetching {program_url} (handle: {handle}): {request_error}")
        return None
    except ValueError as parse_error:
        print(f"Error parsing JSON response for {program_url}: {parse_error}")
        return None

def crawl_hackerone_programs():
    print("Fetching program list...")
    program_links = get_program_links()
    if not program_links:
        print("No programs found or error occurred.")
        return []

    all_rewards = []
    for program_index, program_summary in enumerate(program_links, 1):
        print(f"Processing program {program_index}/{len(program_links)}: {program_summary['url']} (handle: {program_summary['handle']})")
        reward_data = extract_rewards(program_summary["url"], program_summary["handle"])
        if reward_data:
            all_rewards.append(reward_data)
        time.sleep(1)

    return all_rewards

def save_to_json(data, filename="hackerone_rewards.json"):
    with open(filename, "w", encoding="utf-8") as file_handle:
        json.dump(data, file_handle, indent=2)
    print(f"Results saved to {filename}")

if __name__ == "__main__":
    results = []
    try:
        results = crawl_hackerone_programs()
        if results:
            save_to_json(results)
        if not results:
            print("No data to save.")
    except KeyboardInterrupt:
        print("\nCrawling interrupted by user. Saving collected data...")
        save_to_json(results)
