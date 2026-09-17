import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

URL_FFC = "https://competitions.ffc.fr/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (SuiviVelo FFC Sync)"
}

print("=== SuiviVelo - LOCALISATION BOUTONS ENGAGEMENT FFC ===")

session = requests.Session()
session.headers.update(HEADERS)

# ---------------------------------------------------------
# 1. Trouver une compétition
# ---------------------------------------------------------

r = session.get(URL_FFC, timeout=30)
r.raise_for_status()

soup = BeautifulSoup(r.text, "html.parser")

competitions = []

for a in soup.find_all("a", href=True):
    url = urljoin(URL_FFC, a["href"])

    if "/calendrier/competition/2026/" in url:
        if url not in competitions:
            competitions.append(url)

print("Compétitions trouvées :", len(competitions))

if not competitions:
    raise RuntimeError("Aucune compétition trouvée")

competition_url = competitions[0]

print("Compétition :", competition_url)

# ---------------------------------------------------------
# 2. Télécharger page
# ---------------------------------------------------------

r = session.get(competition_url, timeout=30)
r.raise_for_status()

html = r.text
soup = BeautifulSoup(html, "html.parser")

# ---------------------------------------------------------
# 3. Chercher TOUS les appels openEngagementWindow
#    dans le HTML brut
# ---------------------------------------------------------

print()
print("=" * 70)
print("APPELS openEngagementWindow")
print("=" * 70)

pattern = re.compile(
    r'.{0,1500}openEngagementWindow\s*\([^)]*\).{0,1500}',
    re.IGNORECASE | re.DOTALL
)

matches = pattern.findall(html)

print("Nombre de blocs trouvés :", len(matches))

for i, bloc in enumerate(matches, 1):

    print()
    print("######## BLOC", i, "########")
    print(bloc[:4000])

# ---------------------------------------------------------
# 4. Chercher les balises dont onclick contient
#    openEngagementWindow
# ---------------------------------------------------------

print()
print("=" * 70)
print("BALISES CLIQUABLES")
print("=" * 70)

elements = []

for element in soup.find_all(attrs={"onclick": True}):

    onclick = element.get("onclick", "")

    if "openEngagementWindow" in onclick:

        elements.append(element)

print("Nombre de balises :", len(elements))

for i, element in enumerate(elements, 1):

    print()
    print("######## ELEMENT", i, "########")
    print("BALISE :", element.name)
    print("ONCLICK :", element.get("onclick"))

    print("ATTRIBUTS :")

    for key, value in element.attrs.items():
        print(" ", key, "=", value)

    print("TEXTE :", element.get_text(" ", strip=True)[:500])

    print("HTML COMPLET :")
    print(str(element)[:5000])

# ---------------------------------------------------------
# 5. Chercher directement les attributs organisation,
#    epreuve et remplacant dans le HTML brut
# ---------------------------------------------------------

print()
print("=" * 70)
print("OCCURRENCES ATTRIBUT organisation")
print("=" * 70)

for mot in [
    'organisation="',
    "organisation='",
    'epreuve="',
    "epreuve='",
    'remplacant="',
    "remplacant='"
]:

    print()
    print(">>>", mot)

    positions = [
        m.start()
        for m in re.finditer(
            re.escape(mot),
            html,
            re.IGNORECASE
        )
    ]

    print("Occurrences :", len(positions))

    for pos in positions[:20]:

        debut = max(0, pos - 800)
        fin = min(len(html), pos + 1800)

        print()
        print(html[debut:fin])

# ---------------------------------------------------------
# 6. Chercher la génération dynamique des boutons
# ---------------------------------------------------------

print()
print("=" * 70)
print("JAVASCRIPT QUI GENERE LES BOUTONS")
print("=" * 70)

keywords = [
    'attr("organisation"',
    "attr('organisation'",
    'attr("epreuve"',
    "attr('epreuve'",
    'attr("remplacant"',
    "attr('remplacant'",
    "openEngagementWindow(",
    "epreuve-engage"
]

scripts = "\n".join(
    script.get_text("\n", strip=False)
    for script in soup.find_all("script")
    if script.get_text(strip=True)
)

for keyword in keywords:

    print()
    print(">>> RECHERCHE :", keyword)

    lower_scripts = scripts.lower()
    needle = keyword.lower()

    pos = 0
    compteur = 0

    while True:

        pos = lower_scripts.find(needle, pos)

        if pos == -1:
            break

        compteur += 1

        debut = max(0, pos - 2500)
        fin = min(
            len(scripts),
            pos + len(keyword) + 3500
        )

        print()
        print("--- OCCURRENCE", compteur, "---")
        print(scripts[debut:fin])

        pos += len(keyword)

        if compteur >= 10:
            break

    print("TOTAL AFFICHÉ :", compteur)

print()
print("=== FIN LOCALISATION ===")
