import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

URL_FFC = "https://competitions.ffc.fr/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (SuiviVelo FFC Sync)"
}

print("=== SuiviVelo - RECHERCHE IDENTIFIANTS EPREUVES FFC ===")

session = requests.Session()
session.headers.update(HEADERS)

# ---------------------------------------------------------
# 1. Page principale
# ---------------------------------------------------------

response = session.get(URL_FFC, timeout=30)

print("Page principale HTTP :", response.status_code)

response.raise_for_status()

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
    raise RuntimeError("Aucune compétition trouvée.")

competition_url = competitions[0]

print()
print("COMPÉTITION TEST :")
print(competition_url)

# ---------------------------------------------------------
# 3. Télécharger la compétition
# ---------------------------------------------------------

response = session.get(
    competition_url,
    timeout=30
)

print("HTTP :", response.status_code)

response.raise_for_status()

html = response.text

soup = BeautifulSoup(html, "html.parser")

# ---------------------------------------------------------
# 4. Afficher toutes les balises contenant le mot epreuve
# ---------------------------------------------------------

print()
print("================================================")
print("BALISES HTML LIÉES AUX EPREUVES")
print("================================================")

count = 0

for element in soup.find_all(True):

    texte_element = str(element)

    attrs = str(element.attrs)

    recherche = (
        element.name
        + " "
        + attrs
    ).lower()

    if (
        "epreuve" in recherche
        or "engagement" in recherche
        or "organisation" in recherche
    ):

        # On privilégie les petites balises
        if len(texte_element) <= 3000:

            count += 1

            print()
            print("----- ELEMENT", count, "-----")
            print(texte_element[:3000])

            if count >= 100:
                break

print()
print("Nombre d'éléments affichés :", count)

# ---------------------------------------------------------
# 5. Chercher toutes les occurrences de "epreuve"
#    directement dans le HTML brut
# ---------------------------------------------------------

print()
print("================================================")
print("CONTEXTE AUTOUR DE 'epreuve'")
print("================================================")

lower_html = html.lower()

positions = [
    match.start()
    for match in re.finditer(
        "epreuve",
        lower_html
    )
]

print("Occurrences trouvées :", len(positions))

for numero, position in enumerate(
    positions[:30],
    1
):

    debut = max(
        0,
        position - 1000
    )

    fin = min(
        len(html),
        position + 2000
    )

    print()
    print(
        "========== OCCURRENCE",
        numero,
        "=========="
    )

    print(
        html[debut:fin]
    )

# ---------------------------------------------------------
# 6. Rechercher des identifiants numériques potentiels
# ---------------------------------------------------------

print()
print("================================================")
print("ATTRIBUTS DATA-*")
print("================================================")

data_attrs = set()

for element in soup.find_all(True):

    for key, value in element.attrs.items():

        if key.startswith("data-"):

            data_attrs.add(
                (
                    key,
                    str(value)
                )
            )

for key, value in sorted(data_attrs):

    print(
        key,
        "=",
        value[:500]
    )

# ---------------------------------------------------------
# 7. Rechercher onclick
# ---------------------------------------------------------

print()
print("================================================")
print("ONCLICK LIÉS AUX ENGAGEMENTS")
print("================================================")

onclick_found = 0

for element in soup.find_all(
    attrs={"onclick": True}
):

    onclick = element.get("onclick", "")

    if (
        "engagement" in onclick.lower()
        or "epreuve" in onclick.lower()
    ):

        onclick_found += 1

        print()
        print("BALISE :", element.name)
        print("ONCLICK :", onclick)
        print(
            "HTML :",
            str(element)[:2000]
        )

if onclick_found == 0:
    print("Aucun onclick correspondant.")

# ---------------------------------------------------------
# 8. Rechercher les appels openEngagementWindow
# ---------------------------------------------------------

print()
print("================================================")
print("RECHERCHE openEngagementWindow")
print("================================================")

mot = "openEngagementWindow"

start = 0
numero = 0

while True:

    position = html.find(
        mot,
        start
    )

    if position == -1:
        break

    numero += 1

    debut = max(
        0,
        position - 1500
    )

    fin = min(
        len(html),
        position + 2500
    )

    print()
    print(
        "========== RESULTAT",
        numero,
        "=========="
    )

    print(
        html[debut:fin]
    )

    start = position + len(mot)

    if numero >= 20:
        break

print()
print("=== FIN RECHERCHE IDENTIFIANTS ===")
