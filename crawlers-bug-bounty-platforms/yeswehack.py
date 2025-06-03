import requests
from bs4 import BeautifulSoup
import time
import re
import json
from urllib.parse import urljoin

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive"
}

base_url = "https://yeswehack.com"
programs_url = "https://yeswehack.com/programs?page=1&resultsPerPage=74"

def get_program_links(url):
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        print(f"HTTP Status: {response.status_code}, URL: {response.url}")
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        program_cards = soup.select("a[href*='/programs/']")
        program_links = list({urljoin(base_url, card["href"]) for card in program_cards if "/programs/" in card["href"] and not card["href"].endswith("/programs")})
        
        print(f"Found {len(program_links)} unique program links")
        if len(program_links) == 0:
            all_links = soup.select("a[href]")
            print("Sample of <a> tags found:")
            for link in all_links[:10]:
                print(f"- {link.get('href')}")
        
        return program_links
    except requests.RequestException as e:
        print(f"Error fetching program list: {e}")
        return []

def extract_rewards(program_url):
    try:
        response = requests.get(program_url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        reward_data = {
            "program_url": program_url,
            "program_name": program_url.split("/")[-1],
            "rewards": {},
            "bounty": False,
            "hall_of_fame": False
        }
        
        reward_section = soup.find("div", class_=re.compile("d-flex flex-wrap mt-3 gap-3"))
        if reward_section:
            tags = reward_section.find_all("span", class_="tag-content")
            for tag in tags:
                text = tag.get_text(strip=True).lower()
                if text == "bounty":
                    reward_data["bounty"] = True
                if text == "hall of fame":
                    reward_data["hall_of_fame"] = True

        reward_grid = soup.find("ywh-reward-grid")
        if not reward_grid:
            print(f"No reward grid found for {program_url}")
            return reward_data

        titles = reward_grid.find_all("span", class_="reward-grid-title")
        values = reward_grid.find_all("span", class_="reward-grid-value")
        
        for title, value in zip(titles, values):
            severity = title.get_text(strip=True)
            amount = value.find("span", class_="tag-content")
            if amount:
                reward_data["rewards"][severity] = amount.get_text(strip=True)

        return reward_data
    except requests.RequestException as e:
        print(f"Error fetching {program_url}: {e}")
        return None

def crawl_yeswehack_programs():
    print("Fetching program list...")
    program_links = get_program_links(programs_url)
    if not program_links:
        print("No programs found or error occurred.")
        return []

    all_rewards = []
    for i, link in enumerate(program_links, 1):
        print(f"Processing program {i}/{len(program_links)}: {link}")
        reward_data = extract_rewards(link)
        if reward_data:
            all_rewards.append(reward_data)
        time.sleep(1)  

    return all_rewards

def save_to_json(data, filename="yeswehack_rewards.json"):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Results saved to {filename}")

if __name__ == "__main__":
    try:
        results = crawl_yeswehack_programs()
        if results:
            save_to_json(results)
        else:
            print("No data to save.")
    except KeyboardInterrupt:
        print("\nCrawling interrupted by user. Saving collected data...")
        save_to_json(results)
