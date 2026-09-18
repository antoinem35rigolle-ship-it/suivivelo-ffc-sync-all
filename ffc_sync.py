import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

PAGE_URL = "https://competitions.ffc.fr/calendrier/competition/2026/5313014001"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    )
}


def afficher_contexte(source, texte, position, avant=500, apres=1000):
    debut = max(0, position - avant)
    fin = min(len(texte), position + apres)

    print("\n" + "=" * 100)
    print("SOURCE :", source)
    print("=" * 100)
    print(texte[debut:fin])


def main():

    print("=== SuiviVelo - RECHERCHE IDENTIFIANTS INTERNES FFC ===")

    session = requests.Session()
    session.headers.update(HEADERS)

    # ---------------------------------------------------------
    # 1. Charger la page
    # ---------------------------------------------------------

    response = session.get(PAGE_URL, timeout=30)

    print("\nPage :", PAGE_URL)
    print("HTTP :", response.status_code)

    response.raise_for_status()

    html = response.text
    soup = BeautifulSoup(html, "html.parser")

    sources = [
        ("HTML PAGE COMPETITION", html)
    ]

    # ---------------------------------------------------------
    # 2. Charger tous les scripts
    # ---------------------------------------------------------

    print("\n=== CHARGEMENT JAVASCRIPT ===")

    numero = 0

    for script in soup.find_all("script"):

        src = script.get("src")

        if src:

            numero += 1

            url = urljoin(PAGE_URL, src)

            try:

                js_response = session.get(url, timeout=30)

                print(
                    f"JS externe #{numero} : "
                    f"{url} -> HTTP {js_response.status_code}"
                )

                if js_response.status_code == 200:
                    sources.append(
                        (f"JS EXTERNE #{numero} - {url}", js_response.text)
                    )

            except Exception as exc:

                print(
                    f"ERREUR JS externe #{numero} : {exc}"
                )

        else:

            contenu = script.get_text()

            if contenu.strip():

                numero += 1

                sources.append(
                    (f"SCRIPT INLINE #{numero}", contenu)
                )

    # ---------------------------------------------------------
    # 3. Chercher des attributs HTML directement
    # ---------------------------------------------------------

    print("\n=== ATTRIBUTS HTML TROUVES ===")

    compteur = 0

    for tag in soup.find_all(True):

        attrs = tag.attrs

        interessantes = {}

        for cle in [
            "organisation",
            "epreuve",
            "remplacant",
            "onclick",
            "data-organisation",
            "data-epreuve"
        ]:

            if cle in attrs:
                interessantes[cle] = attrs[cle]

        if interessantes:

            compteur += 1

            print("\nELEMENT", compteur)
            print(tag.name)
            print(interessantes)
            print(str(tag)[:2000])

    print("\nNombre d'elements :", compteur)

    # ---------------------------------------------------------
    # 4. Recherche ciblée
    # ---------------------------------------------------------

    recherches = [

        r'openEngagementWindow',

        r'\.attr\(["\']epreuve["\']',

        r'\.attr\(["\']organisation["\']',

        r'\.attr\(["\']remplacant["\']',

        r'epreuve\s*[:=]',

        r'organisation\s*[:=]',

        r'remplacant\s*[:=]',

        r'epreuve["\']\s*,' ,

        r'organisation["\']\s*,' ,

        r'remplacant["\']\s*,' ,

        r'epreuve-main-engages',

        r'epreuve-engage',

        r'engagements\.getEngagementInfos',

        r'engagements\.',

        r'getEpreuve',

        r'getEpreuves',

        r'epreuvesContenu'
    ]

    print("\n=== RECHERCHE DANS HTML + JAVASCRIPT ===")

    total = 0

    for source_name, texte in sources:

        for pattern in recherches:

            try:

                matches = list(
                    re.finditer(
                        pattern,
                        texte,
                        flags=re.IGNORECASE
                    )
                )

            except re.error:
                continue

            if not matches:
                continue

            print(
                f"\n>>> {source_name}"
                f" | motif={pattern}"
                f" | occurrences={len(matches)}"
            )

            for match in matches[:10]:

                total += 1

                afficher_contexte(
                    source_name,
                    texte,
                    match.start(),
                    avant=700,
                    apres=1400
                )

    # ---------------------------------------------------------
    # 5. Recherche des nombres proches des noms d'épreuves
    # ---------------------------------------------------------

    print("\n=== ANALYSE DES EPREUVES ===")

    epreuves = soup.select(".epreuve")

    print("Nombre d'epreuves :", len(epreuves))

    for index, epreuve in enumerate(epreuves, start=1):

        nom_tag = epreuve.select_one(".epreuve-nom")

        nom = (
            nom_tag.get_text(" ", strip=True)
            if nom_tag
            else "INCONNU"
        )

        print("\n" + "-" * 80)
        print("EPREUVE", index)
        print("Nom :", nom)

        print("\nATTRIBUTS DE L'EPREUVE :")
        print(epreuve.attrs)

        print("\nHTML COMPLET DE L'EPREUVE :")
        print(str(epreuve)[:10000])

        # Tous les descendants possédant des attributs
        print("\nDESCENDANTS AVEC ATTRIBUTS :")

        for enfant in epreuve.find_all(True):

            if enfant.attrs:

                print(
                    enfant.name,
                    enfant.attrs
                )

    # ---------------------------------------------------------
    # 6. Recherche de chaînes ressemblant à des identifiants
    # ---------------------------------------------------------

    print("\n=== VALEURS AUTOUR DE openEngagementWindow ===")

    for source_name, texte in sources:

        for match in re.finditer(
            r'openEngagementWindow',
            texte,
            flags=re.IGNORECASE
        ):

            afficher_contexte(
                source_name,
                texte,
                match.start(),
                avant=1500,
                apres=3000
            )

    print("\n=== FIN ANALYSE ===")
    print("Contextes trouves :", total)


if __name__ == "__main__":
    main()
