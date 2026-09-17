import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

URL_FFC = "https://competitions.ffc.fr/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (SuiviVelo FFC Sync)"
}

print("=== SuiviVelo - Recherche API engagements FFC ===")

# ---------------------------------------------------------
# 1. Récupération de la page principale
# ---------------------------------------------------------

session = requests.Session()
session.headers.update(HEADERS)

response = session.get(
    URL_FFC,
    timeout=30
)

print("Page principale HTTP :", response.status_code)

if response.status_code != 200:
    raise RuntimeError(
        f"Impossible de contacter la FFC : HTTP {response.status_code}"
    )

soup = BeautifulSoup(response.text, "html.parser")

# ---------------------------------------------------------
# 2. Trouver une compétition 2026
# ---------------------------------------------------------

competitions = []

for a in soup.find_all("a", href=True):

    href = urljoin(URL_FFC, a["href"])

    if "/calendrier/competition/2026/" in href:
        if href not in competitions:
            competitions.append(href)

print("Compétitions 2026 trouvées :", len(competitions))

if not competitions:
    raise RuntimeError(
        "Aucune compétition 2026 trouvée."
    )

competition_url = competitions[0]

print()
print("=== COMPÉTITION TEST ===")
print(competition_url)

# ---------------------------------------------------------
# 3. Ouvrir la compétition
# ---------------------------------------------------------

response = session.get(
    competition_url,
    timeout=30
)

print("HTTP :", response.status_code)

if response.status_code != 200:
    raise RuntimeError(
        f"Impossible d'ouvrir la compétition : HTTP {response.status_code}"
    )

competition_soup = BeautifulSoup(
    response.text,
    "html.parser"
)

print(
    "Titre :",
    competition_soup.title.get_text(" ", strip=True)
    if competition_soup.title
    else "Sans titre"
)

# ---------------------------------------------------------
# 4. Récupérer tous les scripts
# ---------------------------------------------------------

scripts = []

for script in competition_soup.find_all("script"):

    content = script.get_text("\n", strip=False)

    if content.strip():
        scripts.append(content)

javascript = "\n".join(scripts)

print()
print("Taille JavaScript analysée :", len(javascript), "caractères")

# ---------------------------------------------------------
# 5. Fonction permettant d'afficher du contexte
# ---------------------------------------------------------

def show_context(keyword, before=2500, after=5000):

    print()
    print("=" * 70)
    print("RECHERCHE :", keyword)
    print("=" * 70)

    lower_js = javascript.lower()
    lower_keyword = keyword.lower()

    start = 0
    count = 0

    while True:

        pos = lower_js.find(
            lower_keyword,
            start
        )

        if pos == -1:
            break

        count += 1

        context_start = max(
            0,
            pos - before
        )

        context_end = min(
            len(javascript),
            pos + len(keyword) + after
        )

        print()
        print(
            f">>> OCCURRENCE {count} "
            f"à la position {pos}"
        )

        print(
            javascript[
                context_start:context_end
            ]
        )

        print()
        print("--- FIN CONTEXTE ---")

        start = pos + len(keyword)

        # Éviter un log gigantesque
        if count >= 5:
            print(
                "Maximum de 5 occurrences affichées."
            )
            break

    if count == 0:
        print("Aucune occurrence trouvée.")

# ---------------------------------------------------------
# 6. Recherches importantes
# ---------------------------------------------------------

show_context(
    "updateEngagementInfos",
    before=3000,
    after=7000
)

show_context(
    "tableEngagement",
    before=2500,
    after=6000
)

show_context(
    'formData.append("action"',
    before=2000,
    after=5000
)

show_context(
    "competitionHandlerURL",
    before=2000,
    after=5000
)

# ---------------------------------------------------------
# 7. Extraire toutes les ACTIONS envoyées au handler
# ---------------------------------------------------------

print()
print("=" * 70)
print("ACTIONS DÉTECTÉES")
print("=" * 70)

import re

actions = re.findall(
    r'formData\.append\s*\(\s*["\']action["\']\s*,\s*["\']([^"\']+)["\']',
    javascript,
    flags=re.IGNORECASE
)

unique_actions = []

for action in actions:
    if action not in unique_actions:
        unique_actions.append(action)

if unique_actions:

    for action in unique_actions:
        print("ACTION :", action)

else:
    print("Aucune action détectée.")

# ---------------------------------------------------------
# 8. Rechercher les paramètres liés aux engagements
# ---------------------------------------------------------

print()
print("=" * 70)
print("PARAMÈTRES FORMDATA")
print("=" * 70)

params = re.findall(
    r'formData\.append\s*\(\s*["\']([^"\']+)["\']',
    javascript,
    flags=re.IGNORECASE
)

unique_params = []

for param in params:

    if param not in unique_params:
        unique_params.append(param)

for param in unique_params:
    print("PARAMÈTRE :", param)

# ---------------------------------------------------------
# FIN
# ---------------------------------------------------------

print()
print("=== FIN ANALYSE API FFC ===")
