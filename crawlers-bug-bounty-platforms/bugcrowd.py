import json
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://bugcrowd.com"
MAX_PAGES = 9
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
)


def build_default_headers():
    return {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "sec-ch-ua-platform": "\"macOS\"",
        "sec-ch-ua": "\"Google Chrome\";v=\"137\", \"Chromium\";v=\"137\", \"Not/A)Brand\";v=\"24\"",
        "sec-ch-ua-mobile": "?0",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    }


def initialize_session_and_csrf():
    session = requests.Session()
    default_headers = build_default_headers()
    print("Initializing session and fetching CSRF token...")
    try:
        initial_url = urljoin(BASE_URL, "/engagements")
        html_page_headers = {
            "User-Agent": default_headers["User-Agent"],
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
                "image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
            ),
            "Accept-Language": default_headers["Accept-Language"],
            "Connection": "keep-alive",
        }
        response = session.get(initial_url, headers=html_page_headers, timeout=20)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        csrf_meta_tag = soup.find("meta", attrs={"name": "csrf-token"})

        csrf_token = None
        if csrf_meta_tag and csrf_meta_tag.get("content"):
            csrf_token = csrf_meta_tag["content"]
            print(f"CSRF Token obtained: {csrf_token[:20]}...")
            default_headers["x-csrf-token"] = csrf_token
        if not csrf_token:
            print("Warning: CSRF token meta tag not found. Proceeding without x-csrf-token header.")
    except requests.RequestException as request_error:
        print(f"Error initializing session or fetching CSRF token: {request_error}")
        print("Warning: Proceeding without CSRF token due to initialization error.")
    except Exception as unexpected_error:
        print(f"An unexpected error occurred during session initialization: {unexpected_error}")
    return session, default_headers


def get_program_list_page(session, default_headers, page_number):
    list_url = (
        f"{BASE_URL}/engagements.json?category=bug_bounty"
        f"&page={page_number}&sort_by=promoted&sort_direction=desc"
    )
    request_headers = default_headers.copy()
    request_headers["Referer"] = (
        f"{BASE_URL}/engagements?category=bug_bounty"
        f"&page={page_number}&sort_by=promoted&sort_direction=desc"
    )

    print(f"Fetching program list (page {page_number}): {list_url}")
    try:
        response = session.get(list_url, headers=request_headers, timeout=20)
        response.raise_for_status()
        return response.json().get("engagements", [])
    except requests.RequestException as request_error:
        print(f"  Error fetching program list page {page_number}: {request_error}")
    except json.JSONDecodeError as decode_error:
        print(
            "  Error decoding JSON for program list page "
            f"{page_number}: {decode_error}. Response text: {response.text[:200]}"
        )
    return []


def extract_changelog_base_path(html_content, program_html_url):
    soup = BeautifulSoup(html_content, "html.parser")
    target_div = soup.find(
        "div",
        attrs={"data-react-class": "ResearcherEngagementBrief", "data-api-endpoints": True},
    )

    if not target_div:
        print(
            "    Could not find target div with "
            "'data-react-class=\"ResearcherEngagementBrief\"' and "
            f"'data-api-endpoints' for {program_html_url}"
        )
        return None

    api_endpoints_str = target_div.get("data-api-endpoints")
    if not api_endpoints_str:
        print(f"    'data-api-endpoints' attribute is present but empty for {program_html_url}")
        return None

    try:
        api_endpoints_data = json.loads(api_endpoints_str)
    except json.JSONDecodeError as decode_error:
        print(f"    Error decoding data-api-endpoints JSON for {program_html_url}: {decode_error}")
        print(f"    Raw string (first 300 chars): {api_endpoints_str[:300]}")
        return None

    engagement_api = (api_endpoints_data or {}).get("engagementBriefApi") or {}
    changelog_base_path = engagement_api.get("getBriefVersionDocument")
    if changelog_base_path:
        print(f"    Changelog base path from data-api-endpoints: {changelog_base_path}")
        return changelog_base_path

    print(
        "    'engagementBriefApi.getBriefVersionDocument' path not found in "
        f"data-api-endpoints JSON for {program_html_url}"
    )
    if engagement_api:
        print(f"    Found engagementBriefApi: {engagement_api}")
    return None


def extract_program_scopes(details_data, details_json_url):
    scopes = []
    for scope_item in details_data.get("data", {}).get("scope", []):
        if scope_item.get("inScope") and scope_item.get("rewardRangeData"):
            scopes.append(
                {
                    "scope_name": scope_item.get("name"),
                    "reward_range_data": scope_item.get("rewardRangeData"),
                }
            )
    if not scopes:
        print(f"    No in-scope items with rewardRangeData found in JSON response for {details_json_url}")
    return scopes


def get_program_details(session, default_headers, program_brief_url_path):
    program_html_url = urljoin(BASE_URL, program_brief_url_path)
    print(f"  Fetching details for program: {program_html_url}")

    try:
        html_headers = default_headers.copy()
        html_headers["Accept"] = (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8"
        )
        html_headers["Referer"] = f"{BASE_URL}/engagements"

        response_html = session.get(program_html_url, headers=html_headers, timeout=20)
        response_html.raise_for_status()
        changelog_base_path = extract_changelog_base_path(response_html.text, program_html_url)

        if not changelog_base_path:
            print(
                f"    Critical: Could not extract changelog_base_path for {program_brief_url_path}. "
                "Skipping details."
            )
            return None

        details_json_url = urljoin(BASE_URL, changelog_base_path + ".json")

        json_headers = default_headers.copy()
        json_headers["Referer"] = program_html_url

        print(f"    Fetching scope details from: {details_json_url}")
        response_json = session.get(details_json_url, headers=json_headers, timeout=20)
        response_json.raise_for_status()

        details_data = response_json.json()

        if "data" not in details_data or "scope" not in details_data.get("data", {}):
            print(f"    'data.scope' not found or is not as expected in JSON from {details_json_url}")
            return []

        return extract_program_scopes(details_data, details_json_url)

    except requests.RequestException as request_error:
        print(f"    Error during network request for {program_brief_url_path}: {request_error}")
    except json.JSONDecodeError as decode_error:
        print(f"    Error decoding JSON for {program_brief_url_path} (potentially from details_json_url): {decode_error}")
    except Exception as unexpected_error:
        print(f"    An unexpected error occurred processing {program_brief_url_path}: {unexpected_error}")
        import traceback

        traceback.print_exc()
    return None


def crawl_bugcrowd():
    session, default_headers = initialize_session_and_csrf()
    all_program_data = []

    for page_number in range(1, MAX_PAGES + 1):
        print(f"\nProcessing program list page {page_number} of {MAX_PAGES}...")
        engagements_on_page = get_program_list_page(session, default_headers, page_number)

        if not engagements_on_page:
            print(f"No engagements found on page {page_number}. Moving to next page or finishing.")
            time.sleep(1.5)
            continue

        for engagement_summary in engagements_on_page:
            program_name = engagement_summary.get("name")
            brief_url_path = engagement_summary.get("briefUrl")
            reward_summary_overview = engagement_summary.get("rewardSummary")

            if not brief_url_path:
                print(f"  Skipping engagement '{program_name}' due to missing briefUrl.")
                continue

            print(f"\nProcessing program: {program_name} (Path: {brief_url_path})")
            detailed_scopes = get_program_details(session, default_headers, brief_url_path)

            scopes = []
            if detailed_scopes:
                scopes = detailed_scopes
            program_data_entry = {
                "platform": "Bugcrowd",
                "program_name": program_name,
                "program_url": urljoin(BASE_URL, brief_url_path),
                "overall_reward_summary": reward_summary_overview,
                "scopes": scopes,
            }
            all_program_data.append(program_data_entry)

            time.sleep(1.2)

        print(f"Finished processing page {page_number}.")
        time.sleep(2.5)

    return all_program_data


def save_to_json(data, filename="bugcrowd_rewards.json"):
    try:
        with open(filename, "w", encoding="utf-8") as file_handle:
            json.dump(data, file_handle, indent=2, ensure_ascii=False)
        print(f"\nResults successfully saved to {filename}")
    except IOError as io_error:
        print(f"\nError saving data to {filename}: {io_error}")


if __name__ == "__main__":
    collected_data = []
    start_time = time.time()
    exception_caught = None
    try:
        print("Starting Bugcrowd crawler...")
        collected_data = crawl_bugcrowd()

        if collected_data:
            print(f"\nSuccessfully crawled {len(collected_data)} programs from Bugcrowd.")
        if not collected_data:
            print("\nNo data collected from Bugcrowd.")
    except KeyboardInterrupt as keyboard_interrupt:
        print("\nCrawling interrupted by user.")
        exception_caught = keyboard_interrupt
    except Exception as unexpected_error:
        print(f"\nAn unexpected critical error occurred during crawling: {unexpected_error}")
        import traceback

        traceback.print_exc()
        exception_caught = unexpected_error
    finally:
        if collected_data:
            print("Attempting to save any collected data...")
            filename_to_save = "bugcrowd_rewards_final.json"
            if isinstance(exception_caught, KeyboardInterrupt):
                filename_to_save = "bugcrowd_rewards_partial.json"
            if exception_caught is not None and not isinstance(exception_caught, KeyboardInterrupt):
                filename_to_save = "bugcrowd_rewards_error_dump.json"

            save_to_json(collected_data, filename_to_save)
        if not collected_data:
            print("No data was collected to save.")
        end_time = time.time()
        print(f"Total execution time: {end_time - start_time:.2f} seconds.")
