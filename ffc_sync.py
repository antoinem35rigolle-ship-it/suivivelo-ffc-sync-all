import requests
import http.client
import urllib.request
import time

URL = (
    "https://licence.ffc.fr/evenements/competitions/calendrier.aspx"
    "?discipline=5&autourType=ADRESSE&debut=25%2F09%2F2026"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Connection": "close",
}


def afficher_resultat(methode, status, url_finale, contenu):
    print("\n" + "=" * 90)
    print("SUCCES :", methode)
    print("=" * 90)

    print("HTTP :", status)
    print("URL finale :", url_finale)
    print("Taille recue :", len(contenu))

    texte = contenu.decode(
        "utf-8",
        errors="replace"
    )

    print("\n=== DEBUT REPONSE ===")
    print(texte[:15000])
    print("=== FIN EXTRAIT ===")

    return texte


def methode_requests_normale():

    print("\n=== TEST 1 : REQUESTS NORMAL ===")

    session = requests.Session()
    session.headers.update(HEADERS)

    response = session.get(
        URL,
        timeout=(15, 60),
        allow_redirects=True
    )

    return afficher_resultat(
        "requests normal",
        response.status_code,
        response.url,
        response.content
    )


def methode_requests_stream():

    print("\n=== TEST 2 : REQUESTS STREAM ===")

    session = requests.Session()
    session.headers.update(HEADERS)

    response = session.get(
        URL,
        timeout=(15, 60),
        allow_redirects=True,
        stream=True
    )

    morceaux = []

    try:

        for chunk in response.iter_content(
            chunk_size=1024
        ):

            if chunk:
                morceaux.append(chunk)

    except Exception as exc:

        print(
            "Connexion interrompue pendant le stream :",
            repr(exc)
        )

        print(
            "Octets récupérés avant coupure :",
            sum(len(x) for x in morceaux)
        )

    contenu = b"".join(morceaux)

    if not contenu:
        raise RuntimeError(
            "Aucun contenu récupéré en mode stream"
        )

    return afficher_resultat(
        "requests stream / contenu partiel accepté",
        response.status_code,
        response.url,
        contenu
    )


def methode_requests_http10():

    print("\n=== TEST 3 : REQUESTS SANS COMPRESSION ===")

    headers = dict(HEADERS)

    headers["Accept-Encoding"] = "identity"
    headers["Cache-Control"] = "no-cache"

    session = requests.Session()

    response = session.get(
        URL,
        headers=headers,
        timeout=(15, 60),
        allow_redirects=True,
        stream=True
    )

    morceaux = []

    try:

        response.raw.decode_content = False

        while True:

            try:

                data = response.raw.read(1024)

                if not data:
                    break

                morceaux.append(data)

            except http.client.IncompleteRead as exc:

                print(
                    "IncompleteRead intercepté."
                )

                if exc.partial:
                    morceaux.append(exc.partial)

                break

            except Exception as exc:

                print(
                    "Lecture interrompue :",
                    repr(exc)
                )

                break

    finally:
        response.close()

    contenu = b"".join(morceaux)

    if not contenu:
        raise RuntimeError(
            "Aucun contenu récupéré"
        )

    return afficher_resultat(
        "requests lecture brute",
        response.status_code,
        response.url,
        contenu
    )


def methode_urllib():

    print("\n=== TEST 4 : URLLIB ===")

    request = urllib.request.Request(
        URL,
        headers=HEADERS
    )

    response = urllib.request.urlopen(
        request,
        timeout=60
    )

    morceaux = []

    while True:

        try:

            data = response.read(1024)

            if not data:
                break

            morceaux.append(data)

        except http.client.IncompleteRead as exc:

            print(
                "IncompleteRead intercepté par urllib"
            )

            if exc.partial:
                morceaux.append(exc.partial)

            break

        except Exception as exc:

            print(
                "Lecture urllib interrompue :",
                repr(exc)
            )

            break

    contenu = b"".join(morceaux)

    if not contenu:
        raise RuntimeError(
            "urllib : aucun contenu"
        )

    return afficher_resultat(
        "urllib",
        response.status,
        response.geturl(),
        contenu
    )


def main():

    print(
        "=== SuiviVelo - TEST ROBUSTE LICENCE.FFC.FR ==="
    )

    print("\nURL :")
    print(URL)

    methodes = [
        methode_requests_normale,
        methode_requests_stream,
        methode_requests_http10,
        methode_urllib,
    ]

    succes = False

    for numero, methode in enumerate(
        methodes,
        start=1
    ):

        try:

            texte = methode()

            if texte.strip():

                succes = True

                print(
                    "\n>>> PAGE RECUPEREE AVEC LA METHODE",
                    numero
                )

                break

        except Exception as exc:

            print(
                "\nECHEC METHODE",
                numero,
                ":",
                repr(exc)
            )

            time.sleep(2)

    print("\n" + "=" * 90)

    if succes:

        print(
            "RESULTAT : du contenu a été récupéré."
        )

    else:

        print(
            "RESULTAT : aucune méthode n'a permis "
            "de récupérer la page."
        )

    print(
        "=== FIN TEST LICENCE.FFC.FR ==="
    )


if __name__ == "__main__":
    main()
