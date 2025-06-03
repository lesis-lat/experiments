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
}

HEADERS_DETAIL_PAGE = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

DEFAULT_SEVERITY_HEADERS = ["Low", "Medium", "High", "Critical", "Exceptional"]

def clean_bounty_value(value_str):
    if not value_str:
        return None
    cleaned_str = re.sub(r'[^\d\.]', '', str(value_str))
    try:
        if '.' in cleaned_str:
            if cleaned_str.count('.') > 1 or (cleaned_str.count('.') == 1 and len(cleaned_str.split('.')[1]) == 3):
                cleaned_str = cleaned_str.replace('.', '')
                return int(cleaned_str)
            return float(cleaned_str)
        return int(cleaned_str)
    except ValueError:
        return None

def extract_initial_search_results(html_content):
    prefix = 'window[Symbol.for("InstantSearchInitialResults")]'
    try:
        assignment_start_index = html_content.find(prefix)
        if assignment_start_index == -1: return None
        equals_index = html_content.find('=', assignment_start_index + len(prefix))
        if equals_index == -1: return None
        json_start_index = html_content.find('{', equals_index + 1)
        if json_start_index == -1: return None

        brace_level = 0
        for i in range(json_start_index, len(html_content)):
            char = html_content[i]
            if char == '{': brace_level += 1
            elif char == '}':
                brace_level -= 1
                if brace_level == 0:
                    json_str = html_content[json_start_index : i+1]
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError as e:
                        print(f"Error decoding JSON (post-brace-counting): {e}")
                        return None
        return None
    except Exception as e_gen:
        print(f"Generic error during JSON extraction: {e_gen}")
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
        print(f"Could not find expected JSON structure on page {page_num}.")
        return []
    except requests.RequestException as e:
        print(f"Error fetching page {page_num} ({url}): {e}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred processing page {page_num}: {e}")
        return []

def get_details_from_program_page(detail_page_url, session):
    print(f"  Fetching details for: {detail_page_url}")
    details = {'is_vdp': False, 'detailed_bounties': []}
    try:
        response = session.get(detail_page_url, headers=HEADERS_DETAIL_PAGE, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        vdp_message_tag = soup.find("p", class_="responsible-disclosure")
        if vdp_message_tag and "responsible disclosure program without bounties" in vdp_message_tag.get_text(strip=True).lower():
            details['is_vdp'] = True
            return details

        bounties_section_header = soup.find(lambda tag: tag.name == "div" and "detail-header" in tag.get("class", []) and "Bounties" in tag.get_text())
        if not bounties_section_header:
            if not soup.find("lib-bounty-table-header") and not soup.find("lib-bounty-table-row"):
                details['is_vdp'] = True
            return details 

        bounties_content = bounties_section_header.find_next_sibling("div", class_="detail-content")
        if not bounties_content:
            return details

        severity_headers = []
        header_element = bounties_content.find("lib-bounty-table-header")
        if header_element:
            column_labels = header_element.select("div.column-container div.column div.column-label")
            severity_headers = [label.get_text(strip=True) for label in column_labels]

        if not severity_headers:
            first_row_for_cols = bounties_content.find("lib-bounty-table-row")
            if first_row_for_cols:
                num_cols = len(first_row_for_cols.select("div.column-container div.column"))
                if num_cols == 5:
                    severity_headers = DEFAULT_SEVERITY_HEADERS
                elif num_cols == 4:
                    severity_headers = DEFAULT_SEVERITY_HEADERS[:-1] 

        table_rows = bounties_content.find_all("lib-bounty-table-row")
        for row_element in table_rows:
            tier_data = {"tier_name": "Default", "currency": None, "rewards": {}}
            
            row_label_div = row_element.find("div", class_="row-label")
            if row_label_div:
                tier_label_tag = row_label_div.find("lib-bounty-tier-label")
                if tier_label_tag:
                    tier_name_tag = tier_label_tag.find("div", class_="copy")
                    if tier_name_tag:
                        tier_data["tier_name"] = tier_name_tag.get_text(strip=True)
                
                currency_tag = row_label_div.find("div", class_="currency")
                if currency_tag:
                    tier_data["currency"] = currency_tag.get_text(strip=True)

            value_columns = row_element.select("div.column-container div.column")
            if not severity_headers and len(value_columns) == 5:
                severity_headers = DEFAULT_SEVERITY_HEADERS
            elif not severity_headers and len(value_columns) == 4:
                severity_headers = DEFAULT_SEVERITY_HEADERS[:-1]

            if severity_headers and len(value_columns) == len(severity_headers):
                for i, col_val_element in enumerate(value_columns):
                    range_container = col_val_element.find("div", class_="range-container")
                    if range_container:
                        value_div = range_container.find("div")
                        if value_div:
                            raw_value = value_div.get_text(strip=True)
                            first_number_match = re.match(r'([\d,]+(?:\.\d+)?)', raw_value)
                            if first_number_match:
                                bounty_val = clean_bounty_value(first_number_match.group(1))
                                if bounty_val is not None:
                                    tier_data["rewards"][severity_headers[i]] = bounty_val
                            elif clean_bounty_value(raw_value) is not None:
                                tier_data["rewards"][severity_headers[i]] = clean_bounty_value(raw_value)

            if tier_data["rewards"]:
                details['detailed_bounties'].append(tier_data)

        if not details['detailed_bounties'] and not details['is_vdp']:
            pass

    except requests.RequestException as e:
        print(f"    Error fetching detail page {detail_page_url}: {e}")
    except Exception as e:
        print(f"    An unexpected error occurred while parsing details for {detail_page_url}: {e}")
        import traceback
        traceback.print_exc()
        
    return details

def crawl_intigriti_programs():
    all_programs_data = []
    
    with requests.Session() as session:
        for page_num in range(1, MAX_PAGES + 1):
            programs_on_page = get_programs_from_page(page_num, session)
            
            if not programs_on_page:
                print(f"No programs found on page {page_num} or error. Continuing.")
                if page_num < MAX_PAGES: time.sleep(1)
                continue 
            
            for prog_hit in programs_on_page:
                program_name = prog_hit.get("name")
                company_handle = prog_hit.get("companyHandle")
                prog_handle = prog_hit.get("handle")

                if not all([program_name, company_handle, prog_handle]):
                    print(f"  Skipping program (missing essential data): {prog_hit.get('objectID', 'N/A')}")
                    continue

                detail_url = f"{INTIGRITI_APP_BASE_URL}/programs/{company_handle}/{prog_handle}/detail"
                page_details = get_details_from_program_page(detail_url, session)
                time.sleep(0.6)

                is_vdp_from_detail = page_details['is_vdp']
                detailed_bounties_parsed = page_details['detailed_bounties']

                min_bounty_obj = prog_hit.get("minBounty", {})
                max_bounty_obj = prog_hit.get("maxBounty", {})
                min_bounty_overview = min_bounty_obj.get("value") if min_bounty_obj else None
                max_bounty_overview = max_bounty_obj.get("value") if max_bounty_obj else None
                currency_overview = (max_bounty_obj.get("currency") or 
                                     min_bounty_obj.get("currency") if min_bounty_obj else None)

                offers_bounties_flag = False
                if not is_vdp_from_detail:
                    if max_bounty_overview is not None and max_bounty_overview > 0:
                        offers_bounties_flag = True
                    elif detailed_bounties_parsed:
                        for tier in detailed_bounties_parsed:
                            if any(val > 0 for val in tier.get("rewards", {}).values()):
                                offers_bounties_flag = True
                                break

                if is_vdp_from_detail:
                    offers_bounties_flag = False

                program_info = {
                    "platform": "Intigriti",
                    "program_name": program_name,
                    "program_url": detail_url,
                    "offers_bounties": offers_bounties_flag,
                    "is_responsible_disclosure_only": is_vdp_from_detail,
                    "min_bounty_overview": min_bounty_overview,
                    "max_bounty_overview": max_bounty_overview,
                    "currency_overview": currency_overview,
                    "raw_program_type_overview": prog_hit.get("programType", ""),
                    "detailed_bounties": detailed_bounties_parsed
                }
                all_programs_data.append(program_info)
                print(f"Processed: {program_name} (Offers Bounties: {offers_bounties_flag}, VDP: {is_vdp_from_detail})")

            print(f"Finished page {page_num}. Programs on page: {len(programs_on_page)}.")
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
            save_to_json(collected_data, "intigriti_partial.json")
