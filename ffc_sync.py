import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re

URL = "https://competitions.ffc.fr/calendrier/competition/2026/5313014001"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    )
}

MOTS = [
    "engage",
    "engagé",
    "engages",
    "engagés",
    "participant",
    "participants",
    "inscrit",
    "inscrits",
    "liste",
    "coureur",
    "coureurs",
    "startlist",
    "start-list",
    "start_list",
]


def main():

    print("=== SuiviVelo - RECHERCHE SOURCES PUBLIQUES ENGAGES FFC ===")

    session = requests.Session()
    session.headers.update(HEADERS)

    r = session.get(URL, timeout=30)
    print("\nPage :", URL)
    print("HTTP :", r.status_code)
    print("Taille :", len(r.content))

    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    # =========================================================
    # 1 - DOCUMENTS ET LIENS PUBLICS
    # =========================================================

    print("\n=== 1. LIENS / DOCUMENTS POTENTIELS ===")

    trouves = 0

    for tag in soup.find_all(href=True):

        href = urljoin(URL, tag.get("href"))
        texte = tag.get_text(" ", strip=True)

        chaine = (texte + " " + href).lower()

        if any(mot.lower() in chaine for mot in MOTS):

            trouves += 1

            print("\n--- LIEN", trouves, "---")
            print("Texte :", texte)
            print("URL   :", href)

    # Certains documents sont ouverts par onclick
    for tag in soup.find_all(onclick=True):

        onclick = tag.get("onclick", "")
        texte = tag.get_text(" ", strip=True)

        chaine = (texte + " " + onclick).lower()

        if any(mot.lower() in chaine for mot in MOTS):

            trouves += 1

            print("\n--- ONCLICK", trouves, "---")
            print("Texte   :", texte)
            print("Onclick :", onclick)

    print("\nTotal liens intéressants :", trouves)

    # =========================================================
    # 2 - TOUS LES DOCUMENTS PDF/XLS/CSV
    # =========================================================

    print("\n=== 2. DOCUMENTS PDF / XLS / CSV ===")

    documents = set()

    patterns = [
        r'https?://[^"\'<>\s]+\.pdf[^"\'<>\s]*',
        r'https?://[^"\'<>\s]+\.xls[x]?[^"\'<>\s]*',
        r'https?://[^"\'<>\s]+\.csv[^"\'<>\s]*',
    ]

    for pattern in patterns:

        for match in re.findall(
            pattern,
            r.text,
            flags=re.IGNORECASE
        ):
            documents.add(match)

    for doc in sorted(documents):
        print(doc)

    print("\nNombre documents directs :", len(documents))

    # =========================================================
    # 3 - SCRIPTS
    # =========================================================

    print("\n=== 3. CHARGEMENT DES JAVASCRIPT ===")

    sources = [("HTML", r.text)]

    for index, script in enumerate(soup.find_all("script"), 1):

        src = script.get("src")

        if src:

            js_url = urljoin(URL, src)

            try:
                jr = session.get(js_url, timeout=30)

                print(
                    "JS",
                    index,
                    "HTTP",
                    jr.status_code,
                    js_url
                )

                if jr.status_code == 200:
                    sources.append(
                        ("JS " + js_url, jr.text)
                    )

            except Exception as exc:
                print("Erreur JS :", repr(exc))

        else:

            texte = script.get_text()

            if texte.strip():
                sources.append(
                    ("INLINE " + str(index), texte)
                )

    # =========================================================
    # 4 - RECHERCHE ENDPOINTS / ACTIONS
    # =========================================================

    print("\n=== 4. RECHERCHE ENDPOINTS DE CONSULTATION ===")

    expressions = [
        "engages",
        "engagés",
        "participants",
        "participant",
        "inscrits",
        "inscriptions",
        "startlist",
        "startList",
        "listeEngages",
        "listeParticipants",
        "getEngages",
        "getParticipants",
        "getInscriptions",
        "getListe",
        ".ashx",
        ".asmx",
        "/api/",
        "$.ajax",
        "$.get",
        "$.post",
        "fetch("
    ]

    compteur = 0

    for nom_source, contenu in sources:

        for expression in expressions:

            for match in re.finditer(
                re.escape(expression),
                contenu,
                flags=re.IGNORECASE
            ):

                compteur += 1

                debut = max(0, match.start() - 700)
                fin = min(
                    len(contenu),
                    match.start() + 1500
                )

                print("\n" + "=" * 90)
                print("SOURCE :", nom_source)
                print("RECHERCHE :", expression)
                print("=" * 90)

                print(contenu[debut:fin])

                # évite un log gigantesque
                if compteur >= 150:
                    break

            if compteur >= 150:
                break

        if compteur >= 150:
            break

    print("\nContextes trouvés :", compteur)

    # =========================================================
    # 5 - ACTIONS DU HANDLER
    # =========================================================

    print("\n=== 5. ACTIONS FFC DETECTEES ===")

    actions = set()

    for nom_source, contenu in sources:

        patterns_actions = [
            r'action["\']?\s*[,=:]\s*["\']([^"\']+)["\']',
            r'formData\.append\(\s*["\']action["\']\s*,\s*["\']([^"\']+)["\']',
        ]

        for pattern in patterns_actions:

            for action in re.findall(
                pattern,
                contenu,
                flags=re.IGNORECASE
            ):
                actions.add(action)

    for action in sorted(actions):
        print(action)

    print("\nNombre actions :", len(actions))

    # =========================================================
    # 6 - RECHERCHE DES DOCUMENTS NOMMES LISTE DES ENGAGES
    # =========================================================

    print("\n=== 6. BLOCS AUTOUR DE 'LISTE DES ENGAGES' ===")

    termes = [
        "Liste des engagés",
        "Liste des engages",
        "LISTE DES ENGAGES",
        "liste engagés",
        "liste engages"
    ]

    for terme in termes:

        for match in re.finditer(
            re.escape(terme),
            r.text,
            flags=re.IGNORECASE
        ):

            debut = max(0, match.start() - 1500)
            fin = min(
                len(r.text),
                match.start() + 2500
            )

            print("\n" + "=" * 90)
            print("TERME :", terme)
            print("=" * 90)
            print(r.text[debut:fin])

    print("\n=== FIN RECHERCHE ===")


if __name__ == "__main__":
    main()
