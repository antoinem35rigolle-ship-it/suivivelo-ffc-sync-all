import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

URL_FFC = "https://competitions.ffc.fr/"

headers = {
    "User-Agent": "Mozilla/5.0 (SuiviVelo FFC Sync)"
}

print("=== SuiviVelo - Recherche des compétitions FFC ===")

response = requests.get(
    URL_FFC,
    headers=headers,
    timeout=30
)

print("Code HTTP :", response.status_code)

if response.status_code != 200:
    raise RuntimeError(
        f"Impossible de contacter la FFC : HTTP {response.status_code}"
    )

soup = BeautifulSoup(response.text, "html.parser")

print("Connexion FFC : OK")
print("Titre :", soup.title.get_text(strip=True) if soup.title else "Aucun titre")

links = []

for a in soup.find_all("a", href=True):
    texte = " ".join(a.stripped_strings)
    href = urljoin(URL_FFC, a["href"])

    if not texte:
        continue

    links.append((texte, href))

print()
print("Nombre de liens trouvés :", len(links))
print("=== Liens détectés sur la page ===")

for i, (texte, href) in enumerate(links[:100], start=1):
    print(f"{i:03d} | {texte[:100]} | {href}")

print()
print("=== Fin analyse FFC ===")
