import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

URL_FFC = "https://competitions.ffc.fr/"

headers = {
    "User-Agent": "Mozilla/5.0 (SuiviVelo FFC Sync)"
}

print("=== SuiviVelo - Analyse Listes d'engagements FFC ===")

# ---------------------------------------------------------
# 1. Page principale FFC
# ---------------------------------------------------------

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

# ---------------------------------------------------------
# 2. Récupérer les fiches compétition 2026
# ---------------------------------------------------------

competitions = []

for a in soup.find_all("a", href=True):
    href = urljoin(URL_FFC, a["href"])

    if "/calendrier/competition/2026/" in href:
        if href not in competitions:
            competitions.append(href)

print("Nombre de compétitions 2026 trouvées :", len(competitions))

if not competitions:
    raise RuntimeError("Aucune compétition 2026 trouvée.")

# ---------------------------------------------------------
# 3. Prendre une compétition test
# ---------------------------------------------------------

competition_url = competitions[0]

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
        f"Impossible d'ouvrir la compétition : "
        f"HTTP {competition_response.status_code}"
    )

competition_soup = BeautifulSoup(
    competition_response.text,
    "html.parser"
)

print(
    "Titre :",
    competition_soup.title.get_text(" ", strip=True)
    if competition_soup.title
    else "Sans titre"
)

# ---------------------------------------------------------
# 4. Trouver précisément "Listes d'engagements"
# ---------------------------------------------------------

print()
print("=== RECHERCHE DE 'LISTES D'ENGAGEMENTS' ===")

found = False

for element in competition_soup.find_all(
    ["a", "button", "div", "span", "li"]
):
    text = " ".join(element.stripped_strings).strip()

    normalized = (
        text.lower()
        .replace("’", "'")
        .replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
    )

    if "liste" in normalized and "engagement" in normalized:

        found = True

        print()
        print(">>> ÉLÉMENT TROUVÉ")
        print("Balise :", element.name)
        print("Texte  :", text[:500])

        print("Attributs :")
        for key, value in element.attrs.items():
            print("   ", key, "=", value)

        if element.name == "a":
            href = element.get("href")

            if href:
                print(
                    "URL directe :",
                    urljoin(competition_url, href)
                )

        # Parent immédiat
        parent = element.parent

        if parent:
            print()
            print("--- HTML DU PARENT ---")
            print(str(parent)[:5000])

# ---------------------------------------------------------
# 5. Chercher aussi les éléments interactifs
# ---------------------------------------------------------

print()
print("=== ÉLÉMENTS INTERACTIFS DE LA PAGE ===")

for element in competition_soup.find_all(
    ["a", "button", "input"]
):

    text = " ".join(element.stripped_strings).strip()

    attrs = " ".join(
        f"{k}={v}"
        for k, v in element.attrs.items()
    )

    search = (text + " " + attrs).lower()

    if (
        "engagement" in search
        or "liste" in search
        or "participant" in search
        or "inscrit" in search
    ):
        print()
        print("Balise :", element.name)
        print("Texte :", text[:300])
        print("Attributs :", element.attrs)

# ---------------------------------------------------------
# 6. Recherche dans les scripts JavaScript
# ---------------------------------------------------------

print()
print("=== RECHERCHE DANS LES SCRIPTS ===")

script_found = False

for script in competition_soup.find_all("script"):

    content = script.get_text(" ", strip=True)

    if not content:
        continue

    lower = content.lower()

    if (
        "engagement" in lower
        or "participant" in lower
        or "inscrit" in lower
    ):
        script_found = True

        print()
        print("--- SCRIPT POTENTIEL ---")
        print(content[:4000])

if not script_found:
    print("Aucun script contenant ces mots.")

# ---------------------------------------------------------
# Résultat
# ---------------------------------------------------------

print()

if found:
    print("OK : rubrique Listes d'engagements localisée.")
else:
    print("ATTENTION : rubrique Listes d'engagements non localisée.")

print("=== Fin analyse FFC ===")
