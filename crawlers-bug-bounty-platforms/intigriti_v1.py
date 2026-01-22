import requests
import time
import json
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

INTIGRITI_BASE_URL = "https://www.intigriti.com"
INTIGRITI_APP_BASE_URL = "https://app.intigriti.com"
PROGRAMS_LIST_PATH = "/researchers/bug-bounty-programs"
MAX_PAGES = 6

HEADERS_MAIN_PAGE = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-User": "?1",
    "Sec-Fetch-Dest": "document",
}

HEADERS_DETAIL_PAGE = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-User": "?1",
    "Sec-Fetch-Dest": "document",
}

def extract_initial_search_results(html_content):
    prefix = 'window[Symbol.for("InstantSearchInitialResults")]'
    try:
        assignment_start_index = html_content.find(prefix)
        if assignment_start_index == -1:
            return None
        equals_index = html_content.find('=', assignment_start_index + len(prefix))
        if equals_index == -1:
            return None
        json_start_index = html_content.find('{', equals_index + 1)
        if json_start_index == -1:
            return None
        brace_level = 0
        for character_index in range(json_start_index, len(html_content)):
            char = html_content[character_index]
            if char == '{':
                brace_level += 1
            if char == '}':
                brace_level -= 1
                if brace_level == 0:
                    json_str = html_content[json_start_index : character_index + 1]
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError as decode_error:
                        print(f"Error decoding JSON (post-brace-counting on extracted string): {decode_error}")
                        print("Problematic JSON string snippet (brace-counted):", json_str[:200] + "..." + json_str[-200:])
                        return None
        return None
    except Exception as general_error:
        print(f"Generic error during JSON extraction process: {general_error}")
        return None

def get_programs_from_page(page_number, session):
    url = urljoin(INTIGRITI_BASE_URL, PROGRAMS_LIST_PATH)
    if page_number != 1:
        url = f"{urljoin(INTIGRITI_BASE_URL, PROGRAMS_LIST_PATH)}?programs_prod%5Bpage%5D={page_number}"
    print(f"Fetching program list page: {url}")
    try:
        response = session.get(url, headers=HEADERS_MAIN_PAGE, timeout=20)
        response.raise_for_status()
        initial_data = extract_initial_search_results(response.text)
        if initial_data and "programs_prod" in initial_data:
            results_data = initial_data["programs_prod"].get("results")
            if results_data and len(results_data) > 0:
                return results_data[0].get("hits", [])
        if not initial_data:
            print(f"Failed to extract JSON data structure from page {page_number}.")
            return []
        if "programs_prod" not in initial_data:
            print(f"'programs_prod' key missing in extracted_data for page {page_number}.")
            return []
        results_data = initial_data["programs_prod"].get("results")
        if not results_data or len(results_data) == 0:
            print(f"'results' array missing or empty in programs_prod for page {page_number}.")
            return []
        hits_data = results_data[0].get("hits", [])
        if not hits_data:
            print(f"'hits' array missing or empty in programs_prod.results[0] for page {page_number}.")
        return []
    except requests.RequestException as request_error:
        print(f"Error fetching page {page_number} ({url}): {request_error}")
        return []
    except Exception as unexpected_error:
        print(f"An unexpected error occurred while processing page {page_number}: {unexpected_error}")
        return []

def check_if_responsible_disclosure_only(detail_page_url, session):
    print(f"  Checking responsible disclosure status for: {detail_page_url}")
    try:
        response = session.get(detail_page_url, headers=HEADERS_DETAIL_PAGE, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        responsible_disclosure_message = soup.find("p", class_="responsible-disclosure")
        if responsible_disclosure_message and "responsible disclosure program without bounties" in responsible_disclosure_message.get_text(strip=True).lower():
            return True
        bounties_header = soup.find(lambda tag: tag.name == "div" and "detail-header" in tag.get("class", []) and "Bounties" in tag.get_text())
        if bounties_header:
            detail_content = bounties_header.find_next_sibling("div", class_="detail-content")
            if detail_content:
                text_content = detail_content.get_text(strip=True).lower()
                if "responsible disclosure program without bounties" in text_content:
                    return True
        return False
    except requests.RequestException as request_error:
        print(f"  Error fetching detail page {detail_page_url} for responsible disclosure check: {request_error}")
        return False 
    except Exception as unexpected_error:
        print(f"  An unexpected error occurred while checking responsible disclosure status for {detail_page_url}: {unexpected_error}")
        return False

def crawl_intigriti_programs():
    all_programs_data = []
    with requests.Session() as session:
        for page_number in range(1, MAX_PAGES + 1):
            programs_on_page = get_programs_from_page(page_number, session)
            if not programs_on_page:
                print(f"No programs found on page {page_number} or error occurred during extraction. Continuing to next page.")
                if page_number < MAX_PAGES:
                    time.sleep(1)
                continue 
            for program_hit in programs_on_page:
                program_name = program_hit.get("name")
                company_handle = program_hit.get("companyHandle")
                program_handle = program_hit.get("handle")
                if not all([program_name, company_handle, program_handle]):
                    print(f"  Skipping program due to missing essential data: {program_hit.get('objectID', 'N/A')}")
                    continue
                detail_url = f"{INTIGRITI_APP_BASE_URL}/programs/{company_handle}/{program_handle}/detail"
                min_bounty_info = program_hit.get("minBounty", {})
                max_bounty_info = program_hit.get("maxBounty", {})
                minimum_bounty_value = None
                maximum_bounty_value = None
                if min_bounty_info:
                    minimum_bounty_value = min_bounty_info.get("value")
                if max_bounty_info:
                    maximum_bounty_value = max_bounty_info.get("value")
                currency = None
                if max_bounty_info and max_bounty_info.get("currency"):
                    currency = max_bounty_info.get("currency")
                if currency is None and min_bounty_info and min_bounty_info.get("currency"):
                    currency = min_bounty_info.get("currency")
                program_type = program_hit.get("programType", "") 
                is_responsible_disclosure_only = False
                has_zero_or_missing_maximum_bounty = maximum_bounty_value is None or maximum_bounty_value == 0
                has_responsible_disclosure = "responsible disclosure" in program_type.lower()
                has_bug_bounty = "bug bounty" in program_type.lower()
                should_check_responsible_disclosure = False
                if has_responsible_disclosure:
                    should_check_responsible_disclosure = True
                if has_zero_or_missing_maximum_bounty and not has_bug_bounty:
                    should_check_responsible_disclosure = True
                if should_check_responsible_disclosure:
                    is_responsible_disclosure_only = check_if_responsible_disclosure_only(detail_url, session)
                    time.sleep(0.5)
                if has_zero_or_missing_maximum_bounty and has_bug_bounty and not should_check_responsible_disclosure:
                    is_responsible_disclosure_only = False
                if is_responsible_disclosure_only:
                    minimum_bounty_value = 0
                    maximum_bounty_value = 0
                program_info = {
                    "platform": "Intigriti",
                    "program_name": program_name,
                    "program_url": detail_url,
                    "offers_bounties": not is_responsible_disclosure_only and (maximum_bounty_value is not None and maximum_bounty_value > 0),
                    "is_responsible_disclosure_only": is_responsible_disclosure_only,
                    "min_bounty": minimum_bounty_value,
                    "max_bounty": maximum_bounty_value,
                    "currency": currency,
                    "raw_program_type": program_type 
                }
                all_programs_data.append(program_info)
                print(f"Processed: {program_name} (Bounties: {program_info['offers_bounties']}, Responsible Disclosure Only: {is_responsible_disclosure_only}, Max: {maximum_bounty_value} {currency})")
            print(f"Finished processing page {page_number}. Found {len(programs_on_page)} programs on this page.")
            if page_number < MAX_PAGES:
                time.sleep(1) 
    return all_programs_data

def save_to_json(data, filename="intigriti_programs.json"):
    with open(filename, "w", encoding="utf-8") as file_handle:
        json.dump(data, file_handle, indent=2, ensure_ascii=False)
    print(f"Results saved to {filename}")

if __name__ == "__main__":
    collected_data = []
    try:
        print("Starting Intigriti program crawler...")
        collected_data = crawl_intigriti_programs()
        if collected_data:
            save_to_json(collected_data)
            print(f"\nSuccessfully crawled {len(collected_data)} programs from Intigriti.")
        if not collected_data:
            print("\nNo data collected from Intigriti.")
    except KeyboardInterrupt:
        print("\nCrawling interrupted by user.")
    finally:
        if collected_data:
            print("Saving partially collected data...")
            save_to_json(collected_data, "intigriti_programs_partial.json")
        print("Crawler finished.")
