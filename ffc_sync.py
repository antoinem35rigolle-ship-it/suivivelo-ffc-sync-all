import requests
from bs4 import BeautifulSoup

URL_FFC = "https://competitions.ffc.fr/"

headers = {
    "User-Agent": "Mozilla/5.0 (SuiviVelo FFC Sync)"
}

print("=== SuiviVelo - Synchronisation FFC ===")

response = requests.get(
    URL_FFC,
    headers=headers,
    timeout=30
)

print("Code HTTP :", response.status_code)

if response.status_code == 200:
    soup = BeautifulSoup(response.text, "html.parser")
    print("Connexion au site FFC : OK")
    print("Titre :", soup.title.get_text(strip=True) if soup.title else "Aucun titre")
else:
    raise RuntimeError(
        f"Impossible de contacter la FFC : HTTP {response.status_code}"
    )
