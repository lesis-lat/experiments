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
        for i in range(json_start_index, len(html_content)):
            char = html_content[i]
            if char == '{':
                brace_level += 1
            elif char == '}':
                brace_level -= 1
                if brace_level == 0:
                    json_str = html_content[json_start_index : i+1]
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError as e:
                        print(f"Error decoding JSON (post-brace-counting on extracted string): {e}")
                        print("Problematic JSON string snippet (brace-counted):", json_str[:200] + "..." + json_str[-200:])
                        return None
        return None
    except Exception as e_gen:
        print(f"Generic error during JSON extraction process: {e_gen}")
        return None

def get_programs_from_page(page_num, session):
    if page_num == 1:
        url = urljoin(INTIGRITI_BASE_URL, PROGRAMS_LIST_PATH)
    else:
        url = f"{urljoin(INTIGRITI_BASE_URL, PROGRAMS_LIST_PATH)}?programs_prod%5Bpage%5D={page_num}"
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
            print(f"Failed to extract JSON data structure from page {page_num}.")
        elif "programs_prod" not in initial_data:
            print(f"'programs_prod' key missing in extracted_data for page {page_num}.")
        else:
            results_data = initial_data["programs_prod"].get("results")
            if not results_data or len(results_data) == 0:
                print(f"'results' array missing or empty in programs_prod for page {page_num}.")
            else:
                print(f"'hits' array missing or empty in programs_prod.results[0] for page {page_num}.")
        return []
    except requests.RequestException as e:
        print(f"Error fetching page {page_num} ({url}): {e}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred while processing page {page_num}: {e}")
        return []

def check_if_responsible_disclosure_only(detail_page_url, session):
    print(f"  Checking VDP status for: {detail_page_url}")
    try:
        response = session.get(detail_page_url, headers=HEADERS_DETAIL_PAGE, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        vdp_message = soup.find("p", class_="responsible-disclosure")
        if vdp_message and "responsible disclosure program without bounties" in vdp_message.get_text(strip=True).lower():
            return True
        bounties_header = soup.find(lambda tag: tag.name == "div" and "detail-header" in tag.get("class", []) and "Bounties" in tag.get_text())
        if bounties_header:
            detail_content = bounties_header.find_next_sibling("div", class_="detail-content")
            if detail_content:
                text_content = detail_content.get_text(strip=True).lower()
                if "responsible disclosure program without bounties" in text_content:
                    return True
        return False
    except requests.RequestException as e:
        print(f"  Error fetching detail page {detail_page_url} for VDP check: {e}")
        return False 
    except Exception as e:
        print(f"  An unexpected error occurred while checking VDP status for {detail_page_url}: {e}")
        return False

def crawl_intigriti_programs():
    all_programs_data = []
    with requests.Session() as session:
        for page_num in range(1, MAX_PAGES + 1):
            programs_on_page = get_programs_from_page(page_num, session)
            if not programs_on_page:
                print(f"No programs found on page {page_num} or error occurred during extraction. Continuing to next page.")
                if page_num < MAX_PAGES:
                    time.sleep(1)
                continue 
            for prog_hit in programs_on_page:
                program_name = prog_hit.get("name")
                company_handle = prog_hit.get("companyHandle")
                prog_handle = prog_hit.get("handle")
                if not all([program_name, company_handle, prog_handle]):
                    print(f"  Skipping program due to missing essential data: {prog_hit.get('objectID', 'N/A')}")
                    continue
                detail_url = f"{INTIGRITI_APP_BASE_URL}/programs/{company_handle}/{prog_handle}/detail"
                min_bounty_obj = prog_hit.get("minBounty", {})
                max_bounty_obj = prog_hit.get("maxBounty", {})
                min_bounty_val = min_bounty_obj.get("value") if min_bounty_obj else None
                max_bounty_val = max_bounty_obj.get("value") if max_bounty_obj else None
                currency = None
                if max_bounty_obj and max_bounty_obj.get("currency"):
                    currency = max_bounty_obj.get("currency")
                elif min_bounty_obj and min_bounty_obj.get("currency"):
                    currency = min_bounty_obj.get("currency")
                program_type = prog_hit.get("programType", "") 
                is_vdp = False
                if (max_bounty_val is None or max_bounty_val == 0) or \
                   "responsible disclosure" in program_type.lower():
                    if "responsible disclosure" in program_type.lower() or \
                       (max_bounty_val is None or max_bounty_val == 0 and "bug bounty" not in program_type.lower()):
                        is_vdp = check_if_responsible_disclosure_only(detail_url, session)
                        time.sleep(0.5)
                    elif (max_bounty_val is None or max_bounty_val == 0) and "bug bounty" in program_type.lower():
                        is_vdp = False 
                if is_vdp: 
                    min_bounty_val = 0
                    max_bounty_val = 0
                program_info = {
                    "platform": "Intigriti",
                    "program_name": program_name,
                    "program_url": detail_url,
                    "offers_bounties": not is_vdp and (max_bounty_val is not None and max_bounty_val > 0),
                    "is_responsible_disclosure_only": is_vdp,
                    "min_bounty": min_bounty_val,
                    "max_bounty": max_bounty_val,
                    "currency": currency,
                    "raw_program_type": program_type 
                }
                all_programs_data.append(program_info)
                print(f"Processed: {program_name} (Bounties: {program_info['offers_bounties']}, VDP: {is_vdp}, Max: {max_bounty_val} {currency})")
            print(f"Finished processing page {page_num}. Found {len(programs_on_page)} programs on this page.")
            if page_num < MAX_PAGES:
                time.sleep(1) 
    return all_programs_data

def save_to_json(data, filename="intigriti_programs.json"):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Results saved to {filename}")

if __name__ == "__main__":
    collected_data = []
    try:
        print("Starting Intigriti program crawler...")
        collected_data = crawl_intigriti_programs()
        if collected_data:
            save_to_json(collected_data)
            print(f"\nSuccessfully crawled {len(collected_data)} programs from Intigriti.")
        else:
            print("\nNo data collected from Intigriti.")
    except KeyboardInterrupt:
        print("\nCrawling interrupted by user.")
    finally:
        if collected_data: 
            print("Saving partially collected data...")
            save_to_json(collected_data, "intigriti_programs_partial.json")
        print("Crawler finished.")
