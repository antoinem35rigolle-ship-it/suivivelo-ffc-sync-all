import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

TEST_URL = "https://competitions.ffc.fr/calendrier/competition/2026/5313014001"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    )
}

# Ce que l'on cherche maintenant :
# l'endroit où la FFC fabrique les épreuves et leurs identifiants.
KEYWORDS = [
    "epreuvesContenu",
    "epreuvesDiv",
    "epreuve-main",
    "epreuve-main-engages",
    "openEngagementWindow",
    "organisation=",
    "epreuve=",
    ".attr(\"organisation\"",
    ".attr(\"epreuve\"",
    "getEpreuves",
    "engagements.get",
    "competitionHandlerURL",
    "$.ajax",
    "FormData",
]


def print_context(source_name, text, keyword, radius=3000, max_hits=5):
    lower = text.lower()
    needle = keyword.lower()

    start = 0
    hits = 0

    while hits < max_hits:
        pos = lower.find(needle, start)

        if pos == -1:
            break

        left = max(0, pos - radius)
        right = min(len(text), pos + len(keyword) + radius)

        print("\n" + "=" * 110)
        print("SOURCE :", source_name)
        print("TERME  :", keyword)
        print("=" * 110)
        print(text[left:right])

        hits += 1
        start = pos + len(keyword)

    return hits


def main():
    print("=== SuiviVelo - LOCALISATION CREATION DES EPREUVES FFC ===")
    print("Page :", TEST_URL)

    session = requests.Session()
    session.headers.update(HEADERS)

    response = session.get(TEST_URL, timeout=30)

    print("HTTP :", response.status_code)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    sources = []

    # ---------------------------------------------------------
    # 1. HTML COMPLET
    # ---------------------------------------------------------

    sources.append(("HTML PAGE COMPETITION", response.text))

    # ---------------------------------------------------------
    # 2. SCRIPTS INLINE + JS EXTERNES
    # ---------------------------------------------------------

    print("\n=== CHARGEMENT DES SCRIPTS ===")

    for index, script in enumerate(soup.find_all("script"), start=1):

        src = script.get("src")

        if src:
            js_url = urljoin(TEST_URL, src)

            try:
                js_response = session.get(js_url, timeout=30)

                print(
                    f"JS externe #{index} : "
                    f"{js_url} -> HTTP {js_response.status_code}"
                )

                if js_response.ok:
                    sources.append(
                        (js_url, js_response.text)
                    )

            except requests.RequestException as exc:
                print(
                    f"ERREUR JS : {js_url} -> {exc}"
                )

        else:
            content = script.get_text("\n")

            if content.strip():
                sources.append(
                    (f"script inline #{index}", content)
                )

    # ---------------------------------------------------------
    # 3. ACTIONS FFC TROUVEES
    # ---------------------------------------------------------

    print("\n=== ACTIONS FFC TROUVEES ===")

    actions = set()

    for source_name, text in sources:

        matches = re.findall(
            r"""["']([A-Za-z0-9_.-]*engagement[A-Za-z0-9_.-]*)["']""",
            text,
            flags=re.IGNORECASE
        )

        for match in matches:
            actions.add(match)

    if actions:
        for action in sorted(actions):
            print(action)
    else:
        print("Aucune action engagement trouvee.")

    # ---------------------------------------------------------
    # 4. TOUS LES formData.append
    # ---------------------------------------------------------

    print("\n=== PARAMETRES ENVOYES AUX HANDLERS ===")

    append_lines = set()

    for source_name, text in sources:

        for line in text.splitlines():

            if "formData.append" in line:

                append_lines.add(
                    f"{source_name} : {line.strip()}"
                )

    if append_lines:
        for line in sorted(append_lines):
            print(line)
    else:
        print("Aucun formData.append trouve.")

    # ---------------------------------------------------------
    # 5. RECHERCHE DES ATTRIBUTS HTML
    # ---------------------------------------------------------

    print("\n=== ELEMENTS HTML AVEC ORGANISATION / EPREUVE ===")

    count = 0

    for element in soup.find_all(True):

        attrs_text = str(element.attrs)

        if (
            "organisation" in attrs_text.lower()
            or "epreuve" in attrs_text.lower()
        ):
            count += 1

            print("\n--- ELEMENT", count, "---")
            print(str(element)[:5000])

    print("\nNombre d'elements :", count)

    # ---------------------------------------------------------
    # 6. RECHERCHE DES CHAINES HTML FABRIQUEES EN JAVASCRIPT
    # ---------------------------------------------------------

    print("\n=== CREATION DYNAMIQUE POSSIBLE DES BOUTONS ===")

    dynamic_patterns = [
        r'organisation[^;\n]{0,500}',
        r'epreuve[^;\n]{0,500}',
        r'openEngagementWindow[^;\n]{0,1000}',
        r'epreuve-main-engages[^;\n]{0,1000}',
    ]

    dynamic_results = set()

    for source_name, text in sources:

        for pattern in dynamic_patterns:

            matches = re.findall(
                pattern,
                text,
                flags=re.IGNORECASE
            )

            for match in matches:

                if len(match.strip()) > 5:
                    dynamic_results.add(
                        f"{source_name} : {match.strip()}"
                    )

    for result in sorted(dynamic_results):
        print("\n", result[:3000])

    # ---------------------------------------------------------
    # 7. CONTEXTES COMPLETS AUTOUR DES TERMES IMPORTANTS
    # ---------------------------------------------------------

    print("\n=== CONTEXTES IMPORTANTS ===")

    total_hits = 0

    for source_name, text in sources:

        for keyword in KEYWORDS:

            total_hits += print_context(
                source_name,
                text,
                keyword
            )

    # ---------------------------------------------------------
    # 8. RECHERCHE SPECIALE :
    #    fonctions qui modifient #epreuvesContenu
    # ---------------------------------------------------------

    print("\n=== RECHERCHE SPECIALE EPREUVESCONTENU ===")

    for source_name, text in sources:

        lower = text.lower()

        for needle in [
            "#epreuvescontenu",
            "epreuvescontenu",
            "#epreuvesdiv",
            "epreuvesdiv"
        ]:

            pos = 0
            occurrence = 0

            while occurrence < 10:

                found = lower.find(
                    needle.lower(),
                    pos
                )

                if found == -1:
                    break

                occurrence += 1

                left = max(
                    0,
                    found - 4000
                )

                right = min(
                    len(text),
                    found + 6000
                )

                print("\n" + "#" * 110)
                print("SOURCE :", source_name)
                print("CIBLE  :", needle)
                print("OCCURRENCE :", occurrence)
                print("#" * 110)

                print(
                    text[left:right]
                )

                pos = found + len(needle)

    print("\n=== FIN ANALYSE ===")
    print(
        "Nombre total de contextes trouves :",
        total_hits
    )


if __name__ == "__main__":
    main()
