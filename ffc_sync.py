import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

URL_FFC = "https://competitions.ffc.fr/"

headers = {
    "User-Agent": "Mozilla/5.0 (SuiviVelo FFC Sync)"
}

print("=== SuiviVelo - Analyse fiche compétition FFC ===")

# 1. Ouvrir la page principale FFC
response = requests.get(
    URL_FFC,
    headers=headers,
    timeout=30
)

print("Page principale - HTTP :", response.status_code)

if response.status_code != 200:
    raise RuntimeError(
        f"Impossible de contacter la FFC : HTTP {response.status_code}"
    )

soup = BeautifulSoup(response.text, "html.parser")

# 2. Chercher les liens des compétitions 2026
competition_links = []

for a in soup.find_all("a", href=True):

    href = urljoin(URL_FFC, a["href"])

    if "/calendrier/competition/2026/" in href:
        if href not in competition_links:
            competition_links.append(href)

print("Nombre de compétitions 2026 trouvées :", len(competition_links))

if not competition_links:
    raise RuntimeError("Aucune fiche compétition 2026 trouvée.")

# 3. Pour le test : ouvrir la première compétition trouvée
competition_url = competition_links[0]

print()
print("=== COMPÉTITION TEST ===")
print("URL :", competition_url)

competition_response = requests.get(
    competition_url,
    headers=headers,
    timeout=30
)

print("HTTP :", competition_response.status_code)

if competition_response.status_code != 200:
    raise RuntimeError(
        f"Impossible d'ouvrir la compétition : HTTP "
        f"{competition_response.status_code}"
    )

competition_soup = BeautifulSoup(
    competition_response.text,
    "html.parser"
)

print()
print("Titre HTML :",
      competition_soup.title.get_text(" ", strip=True)
      if competition_soup.title
      else "Aucun titre")

# 4. Afficher les principaux textes de la fiche
print()
print("=== TEXTES DE LA FICHE ===")

for tag in competition_soup.find_all(
        ["h1", "h2", "h3", "h4", "strong"]):

    text = " ".join(tag.stripped_strings)

    if text:
        print(text[:250])

# 5. Rechercher tous les liens de la fiche
print()
print("=== LIENS DE LA FICHE ===")

links = []

for a in competition_soup.find_all("a", href=True):

    text = " ".join(a.stripped_strings)
    href = urljoin(competition_url, a["href"])

    item = (text, href)

    if item not in links:
        links.append(item)

for i, (text, href) in enumerate(links, start=1):
    print(f"{i:03d} | {text[:100]} | {href}")

# 6. Repérer automatiquement les liens intéressants
print()
print("=== LIENS POTENTIELLEMENT LIÉS AUX ENGAGÉS ===")

keywords = [
    "engag",
    "inscrit",
    "participant",
    "partant",
    "liste",
    "startlist",
    "start-list"
]

found = False

for text, href in links:

    search = (text + " " + href).lower()

    if any(keyword in search for keyword in keywords):

        found = True
        print()
        print("Texte :", text)
        print("URL   :", href)

if not found:
    print("Aucun lien évident vers les engagés détecté.")

# 7. Chercher également ces mots directement dans la page
print()
print("=== MOTS CLÉS PRÉSENTS DANS LA PAGE ===")

page_text = competition_soup.get_text(
    " ",
    strip=True
).lower()

for keyword in keywords:

    if keyword in page_text:
        print("TROUVÉ :", keyword)

print()
print("=== Fin analyse fiche compétition ===")
