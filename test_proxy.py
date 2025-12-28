import httpx

PROXY_URL = "http://6dPrK3hR:VP2zxuMP@154.196.75.167:64380"

with httpx.Client(proxy=PROXY_URL) as client:
    response = client.get("https://api.ipify.org?format=json")
    print(f"IP через прокси: {response.json()}")

    response = client.get("https://api.openai.com")
    print(f"OpenAI статус: {response.status_code}")
