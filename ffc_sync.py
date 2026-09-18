import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, unquote
import re

BASE = "https://competitions.ffc.fr/"
URL = (
    "https://competitions.ffc.fr/competition.aspx"
    "?params=2026%2f5313014001%2fdefault.aspx"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9",
}


def main():

    print("=== SuiviVelo - TEST ANCIENNE PAGE COMPETITION FFC ===")

    session = requests.Session()
    session.headers.update(HEADERS)

    print("\nURL testee :")
    print(URL)

    try:
        r = session.get(
            URL,
            timeout=30,
            allow_redirects=True
        )
    except Exception as exc:
        print("\nERREUR :", repr(exc))
        return

    print("\n=== REPONSE ===")
    print("HTTP :", r.status_code)
    print("URL finale :", r.url)
    print("Taille :", len(r.content))
    print("Content-Type :", r.headers.get("Content-Type"))
    print("Cookies :", session.cookies.get_dict())

    print("\n=== REDIRECTIONS ===")

    if r.history:
        for i, hist in enumerate(r.history, 1):
            print(
                i,
                hist.status_code,
                hist.url,
                "->",
                hist.headers.get("Location")
            )
    else:
        print("Aucune redirection")

    soup = BeautifulSoup(r.text, "html.parser")

    print("\n=== TITRE ===")
    print(
        soup.title.get_text(" ", strip=True)
        if soup.title
        else "Aucun titre"
    )

    # ---------------------------------------------------------
    # TEXTE VISIBLE
    # ---------------------------------------------------------

    texte = soup.get_text(" ", strip=True)

    print("\n=== DEBUT TEXTE VISIBLE ===")
    print(texte[:6000])

    # ---------------------------------------------------------
    # RECHERCHE DE TERMES INTERESSANTS
    # ---------------------------------------------------------

    termes = [
        "engagé",
        "engages",
        "engagés",
        "engagement",
        "liste des engagés",
        "liste des engages",
        "participant",
        "participants",
        "inscrit",
        "inscrits",
        "coureur",
        "coureurs",
        "club",
        "dossard",
        "startlist",
        "start list",
        "résultat",
        "resultat",
    ]

    print("\n=== TERMES TROUVES ===")

    for terme in termes:

        matches = list(
            re.finditer(
                re.escape(terme),
                r.text,
                flags=re.IGNORECASE
            )
        )

        if matches:

            print(
                f"\n>>> {terme} : {len(matches)} occurrence(s)"
            )

            for match in matches[:5]:

                debut = max(0, match.start() - 800)
                fin = min(
                    len(r.text),
                    match.start() + 1600
                )

                print("\n--- CONTEXTE ---")
                print(r.text[debut:fin])

    # ---------------------------------------------------------
    # TOUS LES LIENS
    # ---------------------------------------------------------

    print("\n=== LIENS INTERESSANTS ===")

    compteur = 0

    for a in soup.find_all("a", href=True):

        href = urljoin(r.url, a["href"])
        libelle = a.get_text(" ", strip=True)

        chaine = (
            libelle + " " + href
        ).lower()

        if any(
            mot in chaine
            for mot in [
                "engag",
                "participant",
                "inscri",
                "coureur",
                "liste",
                "result",
                "epreuve",
                "competition",
                "club"
            ]
        ):

            compteur += 1

            print("\nLIEN", compteur)
            print("Texte :", libelle)
            print("URL :", unquote(href))

    print("\nNombre liens intéressants :", compteur)

    # ---------------------------------------------------------
    # IFRAMES
    # ---------------------------------------------------------

    print("\n=== IFRAMES ===")

    iframes = soup.find_all("iframe")

    print("Nombre :", len(iframes))

    for iframe in iframes:

        src = iframe.get("src")

        print(
            "SRC :",
            urljoin(r.url, src) if src else None
        )

    # ---------------------------------------------------------
    # FORMULAIRES
    # ---------------------------------------------------------

    print("\n=== FORMULAIRES ===")

    forms = soup.find_all("form")

    print("Nombre :", len(forms))

    for i, form in enumerate(forms, 1):

        print("\nFORM", i)
        print("Action :", form.get("action"))
        print("Method :", form.get("method"))
        print("ID :", form.get("id"))

    # ---------------------------------------------------------
    # ENDPOINTS DANS LE HTML
    # ---------------------------------------------------------

    print("\n=== ENDPOINTS POTENTIELS ===")

    patterns = [
        r'[^"\'\s<>]+\.aspx[^"\'\s<>]*',
        r'[^"\'\s<>]+\.ashx[^"\'\s<>]*',
        r'[^"\'\s<>]+\.asmx[^"\'\s<>]*',
        r'[^"\'\s<>]+\.json[^"\'\s<>]*',
        r'[^"\'\s<>]+\.xml[^"\'\s<>]*',
        r'[^"\'\s<>]+\.pdf[^"\'\s<>]*',
        r'[^"\'\s<>]+\.csv[^"\'\s<>]*',
        r'[^"\'\s<>]+\.xls[x]?[^"\'\s<>]*',
    ]

    endpoints = set()

    for pattern in patterns:

        for valeur in re.findall(
            pattern,
            r.text,
            flags=re.IGNORECASE
        ):
            endpoints.add(valeur)

    for endpoint in sorted(endpoints):
        print(unquote(endpoint))

    print(
        "\nNombre endpoints potentiels :",
        len(endpoints)
    )

    # ---------------------------------------------------------
    # JAVASCRIPT INLINE : AJAX / POST / GET
    # ---------------------------------------------------------

    print("\n=== JAVASCRIPT / AJAX ===")

    js_complet = "\n".join(
        script.get_text()
        for script in soup.find_all("script")
        if not script.get("src")
    )

    mots_js = [
        "$.ajax",
        "$.get",
        "$.post",
        "fetch(",
        "XMLHttpRequest",
        "engagement",
        "participant",
        "coureur",
        "liste",
    ]

    for mot in mots_js:

        matches = list(
            re.finditer(
                re.escape(mot),
                js_complet,
                flags=re.IGNORECASE
            )
        )

        if matches:

            print(
                "\n>>>",
                mot,
                ":",
                len(matches)
            )

            for match in matches[:10]:

                debut = max(
                    0,
                    match.start() - 700
                )

                fin = min(
                    len(js_complet),
                    match.start() + 1500
                )

                print("\n---")
                print(js_complet[debut:fin])

    print("\n=== FIN TEST ANCIENNE PAGE FFC ===")


if __name__ == "__main__":
    main()
