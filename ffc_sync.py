import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re

URL = (
    "https://licence.ffc.fr/evenements/competitions/calendrier.aspx"
    "?discipline=5&autourType=ADRESSE&debut=25%2F09%2F2026"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    )
}


def contexte(texte, position, avant=500, apres=1000):
    debut = max(0, position - avant)
    fin = min(len(texte), position + apres)
    return texte[debut:fin]


def main():

    print("=== SuiviVelo - ANALYSE LICENCE.FFC.FR ===")

    session = requests.Session()
    session.headers.update(HEADERS)

    # --------------------------------------------------
    # 1. Ouvrir la page
    # --------------------------------------------------

    print("\n=== OUVERTURE PAGE ===")
    print("URL :", URL)

    try:
        response = session.get(
            URL,
            timeout=30,
            allow_redirects=True
        )

    except Exception as exc:
        print("ERREUR :", repr(exc))
        return

    print("HTTP :", response.status_code)
    print("URL finale :", response.url)
    print("Taille :", len(response.content))
    print("Cookies :", session.cookies.get_dict())

    print("\nHistorique redirections :")

    if response.history:
        for r in response.history:
            print(
                r.status_code,
                r.url,
                "->",
                r.headers.get("Location")
            )
    else:
        print("Aucune redirection")

    print("\nContent-Type :", response.headers.get("Content-Type"))

    html = response.text

    # --------------------------------------------------
    # 2. Informations générales
    # --------------------------------------------------

    soup = BeautifulSoup(html, "html.parser")

    print("\n=== PAGE RECUE ===")

    if soup.title:
        print("TITLE :", soup.title.get_text(" ", strip=True))
    else:
        print("TITLE : aucun")

    texte_page = soup.get_text(" ", strip=True)

    print("Longueur texte visible :", len(texte_page))

    print("\nDEBUT TEXTE VISIBLE :")
    print(texte_page[:3000])

    # --------------------------------------------------
    # 3. Formulaires
    # --------------------------------------------------

    print("\n=== FORMULAIRES ===")

    forms = soup.find_all("form")

    print("Nombre :", len(forms))

    for i, form in enumerate(forms, 1):

        print("\nFORMULAIRE", i)

        print("action =", form.get("action"))
        print("method =", form.get("method"))
        print("id =", form.get("id"))

        inputs = form.find_all(
            ["input", "select", "button"]
        )

        for element in inputs[:100]:

            print(
                element.name,
                {
                    "id": element.get("id"),
                    "name": element.get("name"),
                    "value": element.get("value"),
                    "type": element.get("type")
                }
            )

    # --------------------------------------------------
    # 4. Tous les liens
    # --------------------------------------------------

    print("\n=== LIENS ===")

    liens = []

    for a in soup.find_all("a", href=True):

        href = urljoin(response.url, a["href"])

        texte = a.get_text(" ", strip=True)

        liens.append((texte, href))

        print(
            "TEXTE :",
            repr(texte[:150]),
            "| URL :",
            href
        )

    print("\nNombre de liens :", len(liens))

    # --------------------------------------------------
    # 5. Liens intéressants
    # --------------------------------------------------

    print("\n=== LIENS POTENTIELLEMENT INTERESSANTS ===")

    mots_liens = [
        "engag",
        "inscri",
        "participant",
        "coureur",
        "liste",
        "detail",
        "epreuve",
        "competition"
    ]

    nb_interessants = 0

    for texte, href in liens:

        chaine = (texte + " " + href).lower()

        if any(mot in chaine for mot in mots_liens):

            nb_interessants += 1

            print(
                "\nTEXTE :",
                texte
            )

            print(
                "URL :",
                href
            )

    print(
        "\nNombre de liens intéressants :",
        nb_interessants
    )

    # --------------------------------------------------
    # 6. Scripts JavaScript
    # --------------------------------------------------

    print("\n=== JAVASCRIPT ===")

    sources = [
        ("HTML", html)
    ]

    numero_script = 0

    for script in soup.find_all("script"):

        src = script.get("src")

        if src:

            numero_script += 1

            url_js = urljoin(
                response.url,
                src
            )

            try:

                js = session.get(
                    url_js,
                    timeout=30
                )

                print(
                    f"JS #{numero_script}",
                    url_js,
                    "HTTP",
                    js.status_code,
                    "taille",
                    len(js.content)
                )

                if js.status_code == 200:

                    sources.append(
                        (
                            f"JS EXTERNE {url_js}",
                            js.text
                        )
                    )

            except Exception as exc:

                print(
                    "ERREUR JS :",
                    url_js,
                    repr(exc)
                )

        else:

            contenu = script.get_text()

            if contenu.strip():

                numero_script += 1

                sources.append(
                    (
                        f"JS INLINE #{numero_script}",
                        contenu
                    )
                )

    # --------------------------------------------------
    # 7. Recherche mots-clés
    # --------------------------------------------------

    recherches = [
        "engagement",
        "engagements",
        "engage",
        "engages",
        "inscription",
        "inscriptions",
        "participant",
        "participants",
        "coureur",
        "coureurs",
        "licencie",
        "licencies",
        "liste",
        "epreuve",
        "competition",
        "ajax",
        "handler",
        ".ashx",
        ".asmx",
        "webmethod",
        "post",
        "json"
    ]

    print("\n=== RECHERCHE MOTS-CLES ===")

    total = 0

    for source_nom, contenu in sources:

        for mot in recherches:

            matches = list(
                re.finditer(
                    re.escape(mot),
                    contenu,
                    flags=re.IGNORECASE
                )
            )

            if not matches:
                continue

            print(
                "\n",
                "=" * 90
            )

            print(
                "SOURCE :",
                source_nom
            )

            print(
                "MOT :",
                mot
            )

            print(
                "OCCURRENCES :",
                len(matches)
            )

            for match in matches[:10]:

                total += 1

                print(
                    "\n--- CONTEXTE ---"
                )

                print(
                    contexte(
                        contenu,
                        match.start()
                    )
                )

    # --------------------------------------------------
    # 8. Recherche URLs/API dans le code
    # --------------------------------------------------

    print("\n=== URLs / ENDPOINTS DETECTES ===")

    urls_trouvees = set()

    patterns_url = [
        r'https?://[^\s"\'<>]+',
        r'["\']([^"\']+\.ashx[^"\']*)["\']',
        r'["\']([^"\']+\.asmx[^"\']*)["\']',
        r'["\']([^"\']+\.aspx[^"\']*)["\']',
        r'["\']([^"\']+/api/[^"\']*)["\']'
    ]

    for source_nom, contenu in sources:

        for pattern in patterns_url:

            try:

                matches = re.findall(
                    pattern,
                    contenu,
                    flags=re.IGNORECASE
                )

            except Exception:
                continue

            for valeur in matches:

                if isinstance(valeur, tuple):
                    valeur = "".join(valeur)

                valeur = str(valeur)

                if valeur not in urls_trouvees:

                    urls_trouvees.add(valeur)

                    if any(
                        mot in valeur.lower()
                        for mot in [
                            "ffc",
                            "engag",
                            "epreuve",
                            "competition",
                            "api",
                            "handler"
                        ]
                    ):

                        print(valeur)

    # --------------------------------------------------
    # FIN
    # --------------------------------------------------

    print("\n=== FIN ANALYSE LICENCE.FFC.FR ===")

    print(
        "Contextes intéressants trouvés :",
        total
    )


if __name__ == "__main__":
    main()
