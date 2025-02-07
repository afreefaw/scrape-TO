import requests

def fetch_with_persistent_session(search_term):
    url = "https://secure.toronto.ca/council/api/multiple/agenda-items.json?pageNumber=0&pageSize=50&sortOrder=meetingDate%20desc,referenceSort"
    session = requests.Session()

    # Initial headers and cookies
    session.headers.update({
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
        "Origin": "https://secure.toronto.ca",
        "Referer": "https://secure.toronto.ca/council/"
    })

    session.cookies.update({
        "XSRF-TOKEN": "a26f164e-efaf-4f6f-afb6-0227bd40b754",
        "JSESSIONID": "0000DEiUydv_XGlh7Y_hl9ykLyx:1cerdme4g"
    })

    payload = {
        "includeTitle": True,
        "includeSummary": True,
        "includeRecommendations": True,
        "includeDecisions": True,
        "decisionBodyId": None,
        "meetingFromDate": None,
        "meetingToDate": None,
        "word": search_term
    }

    response = session.post(url, json=payload)

    if response.status_code == 200:
        return response.json().get('items', [])
    else:
        print(f"Request failed with status code {response.status_code}: {response.text}")
        return []

# Example usage
agenda_items = fetch_with_persistent_session("test")
for item in agenda_items:
    print(item)
