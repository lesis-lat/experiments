import requests
from bs4 import BeautifulSoup
import json
import time
from urllib.parse import urljoin
import html

BASE_URL = "https://bugcrowd.com"
MAX_PAGES = 9

SESSION = requests.Session()
CSRF_TOKEN = None

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "sec-ch-ua-platform": "\"macOS\"",
    "sec-ch-ua": "\"Google Chrome\";v=\"137\", \"Chromium\";v=\"137\", \"Not/A)Brand\";v=\"24\"",
    "sec-ch-ua-mobile": "?0",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive"
}

def initialize_session_and_csrf():
    global CSRF_TOKEN
    global SESSION
    print("Initializing session and fetching CSRF token...")
    try:
        initial_url = urljoin(BASE_URL, "/engagements")
        html_page_headers = {
            "User-Agent": DEFAULT_HEADERS["User-Agent"],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": DEFAULT_HEADERS["Accept-Language"],
            "Connection": "keep-alive"
        }
        response = SESSION.get(initial_url, headers=html_page_headers, timeout=20)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        csrf_meta_tag = soup.find('meta', attrs={'name': 'csrf-token'})
        
        if csrf_meta_tag and csrf_meta_tag.get('content'):
            CSRF_TOKEN = csrf_meta_tag['content']
            print(f"CSRF Token obtained: {CSRF_TOKEN[:20]}...")
            DEFAULT_HEADERS['x-csrf-token'] = CSRF_TOKEN
        else:
            print("Warning: CSRF token meta tag not found. Proceeding without x-csrf-token header.")
    except requests.RequestException as e:
        print(f"Error initializing session or fetching CSRF token: {e}")
        print("Warning: Proceeding without CSRF token due to initialization error.")
    except Exception as e:
        print(f"An unexpected error occurred during session initialization: {e}")

def get_program_list_page(page_num):
    list_url = f"{BASE_URL}/engagements.json?category=bug_bounty&page={page_num}&sort_by=promoted&sort_direction=desc"
    request_headers = DEFAULT_HEADERS.copy()
    request_headers['Referer'] = f"{BASE_URL}/engagements?category=bug_bounty&page={page_num}&sort_by=promoted&sort_direction=desc"
    
    print(f"Fetching program list (page {page_num}): {list_url}")
    try:
        response = SESSION.get(list_url, headers=request_headers, timeout=20)
        response.raise_for_status()
        return response.json().get("engagements", [])
    except requests.RequestException as e:
        print(f"  Error fetching program list page {page_num}: {e}")
    except json.JSONDecodeError as e:
        print(f"  Error decoding JSON for program list page {page_num}: {e}. Response text: {response.text[:200]}")
    return []

def get_program_details(program_brief_url_path):
    program_html_url = urljoin(BASE_URL, program_brief_url_path)
    print(f"  Fetching details for program: {program_html_url}")
    
    changelog_base_path = None

    try:
        html_headers = DEFAULT_HEADERS.copy()
        html_headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
        html_headers['Referer'] = f"{BASE_URL}/engagements"
        
        response_html = SESSION.get(program_html_url, headers=html_headers, timeout=20)
        response_html.raise_for_status()
        soup = BeautifulSoup(response_html.text, 'html.parser')

        target_div = soup.find('div', attrs={'data-react-class': 'ResearcherEngagementBrief', 'data-api-endpoints': True})

        if target_div:
            api_endpoints_str = target_div.get('data-api-endpoints')
            if api_endpoints_str:
                try:
                    api_endpoints_data = json.loads(api_endpoints_str)
                    if (api_endpoints_data and 
                        'engagementBriefApi' in api_endpoints_data and 
                        api_endpoints_data['engagementBriefApi'] and
                        'getBriefVersionDocument' in api_endpoints_data['engagementBriefApi']):
                        
                        changelog_base_path = api_endpoints_data['engagementBriefApi']['getBriefVersionDocument']
                        if changelog_base_path:
                             print(f"    Changelog base path from data-api-endpoints: {changelog_base_path}")
                        else:
                            print(f"    'getBriefVersionDocument' was empty/null in data-api-endpoints JSON for {program_html_url}")
                    else:
                        print(f"    'engagementBriefApi.getBriefVersionDocument' path not found in data-api-endpoints JSON for {program_html_url}")
                        if api_endpoints_data and 'engagementBriefApi' in api_endpoints_data:
                            print(f"    Found engagementBriefApi: {api_endpoints_data['engagementBriefApi']}")
                except json.JSONDecodeError as e:
                    print(f"    Error decoding data-api-endpoints JSON for {program_html_url}: {e}")
                    print(f"    Raw string (first 300 chars): {api_endpoints_str[:300]}")
            else:
                print(f"    'data-api-endpoints' attribute is present but empty for {program_html_url}")
        else:
            print(f"    Could not find target div with 'data-react-class=\"ResearcherEngagementBrief\"' and 'data-api-endpoints' for {program_html_url}")

        if not changelog_base_path:
            print(f"    Critical: Could not extract changelog_base_path for {program_brief_url_path}. Skipping details.")
            return None
        
        details_json_url = urljoin(BASE_URL, changelog_base_path + ".json")
        
        json_headers = DEFAULT_HEADERS.copy()
        json_headers['Referer'] = program_html_url
        
        print(f"    Fetching scope details from: {details_json_url}")
        response_json = SESSION.get(details_json_url, headers=json_headers, timeout=20)
        response_json.raise_for_status()
        
        details_data = response_json.json()
        
        program_scopes = []
        if 'data' in details_data and 'scope' in details_data['data']:
            for scope_item in details_data['data']['scope']:
                if scope_item.get('inScope', False) and scope_item.get('rewardRangeData'):
                    scope_name = scope_item.get('name')
                    reward_range_data = scope_item.get('rewardRangeData')
                    
                    program_scopes.append({
                        "scope_name": scope_name,
                        "reward_range_data": reward_range_data
                    })
            if not program_scopes:
                 print(f"    No in-scope items with rewardRangeData found in JSON response for {details_json_url}")
        else:
            print(f"    'data.scope' not found or is not as expected in JSON from {details_json_url}")
            
        return program_scopes

    except requests.RequestException as e:
        print(f"    Error during network request for {program_brief_url_path}: {e}")
    except json.JSONDecodeError as e:
        print(f"    Error decoding JSON for {program_brief_url_path} (potentially from details_json_url): {e}")
    except Exception as e:
        print(f"    An unexpected error occurred processing {program_brief_url_path}: {e}")
        import traceback
        traceback.print_exc()
    return None

def crawl_bugcrowd():
    initialize_session_and_csrf()
    all_program_data = []

    for page_num in range(1, MAX_PAGES + 1):
        print(f"\nProcessing program list page {page_num} of {MAX_PAGES}...")
        engagements_on_page = get_program_list_page(page_num)
        
        if not engagements_on_page:
            print(f"No engagements found on page {page_num}. Moving to next page or finishing.")
            time.sleep(1.5)
            continue

        for eng_summary in engagements_on_page:
            program_name = eng_summary.get('name')
            brief_url_path = eng_summary.get('briefUrl')
            reward_summary_overview = eng_summary.get('rewardSummary')
            
            if not brief_url_path:
                print(f"  Skipping engagement '{program_name}' due to missing briefUrl.")
                continue

            print(f"\nProcessing program: {program_name} (Path: {brief_url_path})")
            detailed_scopes = get_program_details(brief_url_path)
            
            program_data_entry = {
                "platform": "Bugcrowd",
                "program_name": program_name,
                "program_url": urljoin(BASE_URL, brief_url_path),
                "overall_reward_summary": reward_summary_overview,
                "scopes": detailed_scopes if detailed_scopes else []
            }
            all_program_data.append(program_data_entry)
            
            time.sleep(1.2)

        print(f"Finished processing page {page_num}.")
        time.sleep(2.5)
        
    return all_program_data

def save_to_json(data, filename="bugcrowd_rewards.json"):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"\nResults successfully saved to {filename}")
    except IOError as e:
        print(f"\nError saving data to {filename}: {e}")

if __name__ == "__main__":
    collected_data = []
    start_time = time.time()
    exception_caught = None
    try:
        print("Starting Bugcrowd crawler...")
        collected_data = crawl_bugcrowd()
        
        if collected_data:
            print(f"\nSuccessfully crawled {len(collected_data)} programs from Bugcrowd.")
        else:
            print("\nNo data collected from Bugcrowd.")
    except KeyboardInterrupt as ki:
        print("\nCrawling interrupted by user.")
        exception_caught = ki
    except Exception as ex:
        print(f"\nAn unexpected critical error occurred during crawling: {ex}")
        import traceback
        traceback.print_exc()
        exception_caught = ex
    finally:
        if collected_data:
            print("Attempting to save any collected data...")
            filename_to_save = "bugcrowd_rewards_final.json"
            if isinstance(exception_caught, KeyboardInterrupt):
                filename_to_save = "bugcrowd_rewards_partial.json"
            elif exception_caught is not None:
                 filename_to_save = "bugcrowd_rewards_error_dump.json"

            save_to_json(collected_data, filename_to_save)
        else:
            print("No data was collected to save.")
        end_time = time.time()
        print(f"Total execution time: {end_time - start_time:.2f} seconds.")
