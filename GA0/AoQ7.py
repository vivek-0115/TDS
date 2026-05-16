import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque
import re

BASE_URL = "https://sanand0.github.io/tdsdata/crawl_html/"

visited = set()
queue = deque([BASE_URL])

count = 0

while queue:
    url = queue.popleft()

    if url in visited:
        continue

    visited.add(url)

    try:
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            continue

        soup = BeautifulSoup(response.text, "html.parser")

        # Count HTML filenames beginning with G-R
        path = urlparse(url).path
        filename = path.split("/")[-1]

        if re.match(r'^[G-Rg-r].*\.html?$', filename):
            count += 1

        # Find more links
        for link in soup.find_all("a", href=True):
            next_url = urljoin(url, link["href"])

            # Stay inside target site only
            if next_url.startswith(BASE_URL):
                if next_url not in visited:
                    queue.append(next_url)

    except Exception:
        pass

print("Number of files:", count)