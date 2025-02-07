import requests
from bs4 import BeautifulSoup

# URL of the agenda item page
url = "https://secure.toronto.ca/council/agenda-item.do?item=2025.TE19.19"

# Fetch the webpage
response = requests.get(url)
soup = BeautifulSoup(response.text, 'html.parser')

# Find all background file links
base_url = "https://www.toronto.ca"  # Base URL for relative links
background_links = []

for a_tag in soup.find_all('a', href=True):
    href = a_tag['href']
    if "backgroundfile" in href:
        if href.startswith("http"):
            background_links.append(href)
        else:
            background_links.append(base_url + href)

# Print the extracted links
for link in background_links:
    print(link)
