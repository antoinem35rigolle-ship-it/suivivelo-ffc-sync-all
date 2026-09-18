import requests

PAGE_URL = "https://competitions.ffc.fr/calendrier/competition/2026/5313014001"
HANDLER_URL = "https://competitions.ffc.fr/handlers/competitions.ashx"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    ),
    "Referer": PAGE_URL,
    "X-Requested-With": "XMLHttpRequest",
}

def main():
    print("=== SuiviVelo - TEST DIRECT HANDLER FFC ===")

    session = requests.Session()
    session.headers.update(HEADERS)

    print("\n1. Ouverture de la page competition")
    page = session.get(PAGE_URL, timeout=30)

    print("HTTP :", page.status_code)
    print("Cookies :", session.cookies.get_dict())

    page.raise_for_status()

    print("\n2. Test engagements.getEngagementInfos")

    tests = [
        {
            "action": "engagements.getEngagementInfos",
            "organisation": "5313014001",
            "epreuve": "1",
            "remplacant": "false",
        },
        {
            "action": "engagements.getEngagementInfos",
            "organisation": "5313014001",
            "epreuve": "0",
            "remplacant": "false",
        },
        {
            "action": "engagements.getEngagementInfos",
            "organisation": "5313014001",
            "epreuve": "",
            "remplacant": "false",
        },
    ]

    for numero, data in enumerate(tests, start=1):

        print("\n" + "=" * 80)
        print("TEST", numero)
        print("=" * 80)

        print("Donnees envoyees :")
        for key, value in data.items():
            print(f"  {key} = {value}")

        try:
            response = session.post(
                HANDLER_URL,
                data=data,
                timeout=30
            )

            print("\nHTTP :", response.status_code)
            print("Content-Type :", response.headers.get("Content-Type"))
            print("Taille reponse :", len(response.content))

            print("\nREPONSE BRUTE :")
            print(response.text[:10000])

        except Exception as exc:
            print("\nERREUR :", repr(exc))

    print("\n=== FIN TEST HANDLER FFC ===")


if __name__ == "__main__":
    main()
