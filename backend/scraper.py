# Updated scrape.py
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/112.0.0.0 Safari/537.36"
    )
}

def scrape_url(url):
    res = requests.get(url, headers=HEADERS)
    if res.status_code != 200:
        print(f"Failed to scrape {url}: {res.status_code}")
        return f"[ERROR {res.status_code}]"
    
    soup = BeautifulSoup(res.text, 'html.parser')
    for script in soup(["script", "style"]):
        script.extract()
    return soup.get_text(separator="\n")

urls = [
    "https://virtourmedia.com/",
    "https://virtourmedia.com/how-it-works/",
    "https://virtourmedia.com/services/",
    "https://virtourmedia.com/industries/",
    "https://virtourmedia.com/blog/",
    "https://virtourmedia.com/contact/",
    "https://agent.virtourmedia.com/order"
]

all_text = ""

for url in urls:
    print(f"Scraping {url}")
    content = scrape_url(url)
    all_text += f"\n\n# {url}\n\n" + content

with open("virtour_content.txt", "w") as f:
    f.write(all_text)

print("✅ Scraping complete.")
