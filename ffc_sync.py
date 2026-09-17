import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

URL_FFC = "https://competitions.ffc.fr/"
HANDLER = "https://competitions.ffc.fr/handlers/competitions.ashx"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (SuiviVelo FFC Sync)"
}

print("=== SuiviVelo - TEST API ENGAGEMENTS FFC ===")

session = requests.Session()
session.headers.update(HEADERS)

# ---------------------------------------------------------
# 1. Page principale
# ---------------------------------------------------------

response = session.get(URL_FFC, timeout=30)

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
    raise RuntimeError("Aucune compétition 2026 trouvée.")

competition_url = competitions[0]

print()
print("=== COMPÉTITION TEST ===")
print("URL :", competition_url)

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
# 4. Chercher les boutons / éléments contenant
#    organisation + epreuve
# ---------------------------------------------------------

print()
print("=== RECHERCHE ORGANISATION / EPREUVE ===")

epreuves = []

for element in competition_soup.find_all(True):

    organisation = element.get("organisation")
    epreuve = element.get("epreuve")

    if organisation and epreuve:

        remplacant = element.get("remplacant", "0")

        cle = (
            organisation,
            epreuve,
            remplacant
        )

        if cle not in [
            (
                x["organisation"],
                x["epreuve"],
                x["remplacant"]
            )
            for x in epreuves
        ]:

            epreuves.append({
                "organisation": organisation,
                "epreuve": epreuve,
                "remplacant": remplacant,
                "texte": " ".join(
                    element.stripped_strings
                ).strip()
            })

print("Nombre de combinaisons trouvées :", len(epreuves))

for index, item in enumerate(epreuves, 1):

    print()
    print("--- EPREUVE", index, "---")
    print("organisation :", item["organisation"])
    print("epreuve      :", item["epreuve"])
    print("remplacant   :", item["remplacant"])
    print("texte        :", item["texte"][:300])

# ---------------------------------------------------------
# 5. Aucun attribut trouvé
# ---------------------------------------------------------

if not epreuves:

    print()
    print("ATTENTION : aucun couple organisation/epreuve trouvé.")
    print("Le HTML devra être analysé différemment.")

    raise SystemExit(0)

# ---------------------------------------------------------
# 6. Tester getEngagementInfos
# ---------------------------------------------------------

print()
print("==============================================")
print("TEST engagements.getEngagementInfos")
print("==============================================")

for index, item in enumerate(epreuves, 1):

    print()
    print("##############################################")
    print("EPREUVE", index)
    print("##############################################")

    payload = {
        "action": "engagements.getEngagementInfos",
        "organisation": item["organisation"],
        "epreuve": item["epreuve"],
        "remplacant": item["remplacant"]
    }

    print("Payload :", payload)

    try:

        api_response = session.post(
            HANDLER,
            data=payload,
            headers={
                "Referer": competition_url,
                "X-Requested-With": "XMLHttpRequest"
            },
            timeout=30
        )

        print("HTTP API :", api_response.status_code)

        print()
        print("--- REPONSE BRUTE ---")

        texte = api_response.text

        # Limite volontaire pour GitHub Actions
        print(texte[:10000])

        print()
        print("--- ANALYSE JSON ---")

        try:

            data = api_response.json()

            print(
                json.dumps(
                    data,
                    indent=2,
                    ensure_ascii=False
                )[:15000]
            )

            # ---------------------------------------------
            # Chercher engagements
            # ---------------------------------------------

            if "engagements" in data:

                engagements_raw = data["engagements"]

                try:

                    if isinstance(engagements_raw, str):
                        engagements = json.loads(
                            engagements_raw
                        )
                    else:
                        engagements = engagements_raw

                    print()
                    print(
                        "NOMBRE D'ENGAGEMENTS :",
                        len(engagements)
                    )

                    print()
                    print("=== COUREURS ===")

                    for engagement in engagements:

                        coureur = engagement.get(
                            "coureur",
                            {}
                        )

                        print(
                            coureur.get("nom", ""),
                            coureur.get("prenom", ""),
                            "|",
                            coureur.get(
                                "categorieComplete",
                                ""
                            ),
                            "| type =",
                            engagement.get(
                                "engagementType"
                            )
                        )

                except Exception as erreur:

                    print(
                        "Impossible de décoder engagements :",
                        erreur
                    )

            else:

                print(
                    "Pas de champ 'engagements' "
                    "dans la réponse."
                )

        except Exception:

            print(
                "La réponse n'est pas un JSON directement décodable."
            )

    except Exception as erreur:

        print(
            "ERREUR pendant l'appel API :",
            erreur
        )

print()
print("=== FIN TEST API ENGAGEMENTS FFC ===")
