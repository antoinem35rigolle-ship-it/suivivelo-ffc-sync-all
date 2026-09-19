import os
import json
import re
import hashlib
import unicodedata
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore

# Course test validée sur VéloPresse.
VELOPRESSE_URL = os.environ.get(
    "VELOPRESSE_URL",
    "https://velopressecollection.ouest-france.fr/route/engages/"
    "38615-pleslin-trigavou-19-septembre-2026-engages-de-course-cycliste.html"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
}

MONTHS = {
    "janvier": 1, "fevrier": 2, "février": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "aout": 8, "août": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12,
    "décembre": 12,
}


def clean(value):
    return re.sub(r"\s+", " ", (value or "")).strip()


def slug(value):
    value = unicodedata.normalize("NFD", clean(value))
    value = "".join(c for c in value if unicodedata.category(c) != "Mn")
    value = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
    return value


def firebase():
    raw = os.environ.get("FIREBASE_SERVICE_ACCOUNT", "").strip()
    if not raw:
        raise RuntimeError("Secret FIREBASE_SERVICE_ACCOUNT absent.")

    info = json.loads(raw)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(info))
    return firestore.client()


def extract_course_info(soup):
    h1 = soup.find("h1")
    title = clean(h1.get_text(" ", strip=True) if h1 else soup.title.get_text(" ", strip=True))

    m = re.search(
        r"(.+?)\s+(\d{1,2})\s+"
        r"(janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[ée]cembre)"
        r"\s+(\d{4})",
        title,
        flags=re.I,
    )
    if not m:
        raise RuntimeError("Date de course introuvable dans le titre VéloPresse.")

    place = clean(m.group(1))
    day = int(m.group(2))
    month = MONTHS[m.group(3).lower()]
    year = int(m.group(4))
    course_date = f"{day:02d}/{month:02d}/{year}"

    course_title = re.sub(
        r"\s+engag[ée]s?.*$",
        "",
        title,
        flags=re.I,
    ).strip()

    discipline = "CYCLOCROSS" if "/cyclo-cross/" in VELOPRESSE_URL.lower() else "ROUTE"
    return course_title, place, course_date, discipline


def parse_rows(soup):
    riders = []

    # VéloPresse publie les engagés sous forme de tableaux.
    for tr in soup.find_all("tr"):
        cells = [clean(x.get_text(" ", strip=True)) for x in tr.find_all(["td", "th"])]
        if len(cells) < 4:
            continue

        # Formats observés :
        # NOM | Prénom | H/F | Catégorie | Club
        # NOM | Prénom | Catégorie | Club
        if len(cells) >= 5 and cells[2].upper() in {"H", "F", "M"}:
            last_name, first_name, sex, category = cells[0], cells[1], cells[2], cells[3]
            club = cells[4]
        else:
            last_name, first_name = cells[0], cells[1]
            sex = ""
            category = cells[-2]
            club = cells[-1]

        category = clean(category).upper()
        if not re.fullmatch(r"U\d{1,2}|OPEN|ACCESS|ELITE|ÉLITE", category, flags=re.I):
            continue
        if not last_name or not first_name or not club:
            continue

        riders.append({
            "lastName": clean(last_name),
            "firstName": clean(first_name),
            "sex": clean(sex).upper(),
            "category": category,
            "club": clean(club),
        })

    # Sécurité : si la mise en page n'utilise plus de <tr>, on tente les lignes
    # textuelles contenant des séparateurs |.
    if not riders:
        text = soup.get_text("\n", strip=True)
        for line in text.splitlines():
            parts = [clean(x) for x in line.split("|")]
            if len(parts) < 4:
                continue
            if len(parts) >= 5 and parts[2].upper() in {"H", "F", "M"}:
                last_name, first_name, sex, category, club = parts[:5]
            else:
                last_name, first_name, category, club = parts[:4]
                sex = ""
            category = category.upper()
            if re.fullmatch(r"U\d{1,2}|OPEN|ACCESS|ELITE|ÉLITE", category, flags=re.I):
                riders.append({
                    "lastName": last_name,
                    "firstName": first_name,
                    "sex": sex.upper(),
                    "category": category,
                    "club": club,
                })

    # Déduplication.
    unique = {}
    for r in riders:
        key = "|".join([
            slug(r["lastName"]), slug(r["firstName"]),
            slug(r["category"]), slug(r["club"])
        ])
        unique[key] = r
    return list(unique.values())


def main():
    print("=== SuiviVélo • VéloPresse -> Firebase ===")
    print("Course :", VELOPRESSE_URL)

    response = requests.get(VELOPRESSE_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    title, place, date, discipline = extract_course_info(soup)
    riders = parse_rows(soup)

    print("Titre      :", title)
    print("Date       :", date)
    print("Lieu       :", place)
    print("Discipline :", discipline)
    print("Engagés    :", len(riders))

    if not riders:
        raise RuntimeError("Aucun engagé détecté : aucune écriture Firebase effectuée.")

    db = firebase()
    collection = db.collection("ffc_engagements")

    # Une actualisation doit refléter la liste VéloPresse actuelle :
    # on retire d'abord les anciens documents issus de CETTE page.
    old = list(collection.where("sourceUrl", "==", VELOPRESSE_URL).stream())
    for start in range(0, len(old), 400):
        batch = db.batch()
        for doc in old[start:start + 400]:
            batch.delete(doc.reference)
        batch.commit()

    now = datetime.now(timezone.utc)
    docs = []
    for rider in riders:
        runner_name = clean(f'{rider["firstName"]} {rider["lastName"]}')
        identity = "|".join([
            VELOPRESSE_URL,
            rider["category"],
            rider["lastName"],
            rider["firstName"],
            rider["club"],
        ])
        doc_id = hashlib.sha1(identity.encode("utf-8")).hexdigest()

        docs.append((
            collection.document(doc_id),
            {
                "title": title,
                "courseTitle": title,
                "date": date,
                "courseDate": date,
                "place": place,
                "discipline": discipline,
                "category": rider["category"],
                "runnerName": runner_name,
                "firstName": rider["firstName"],
                "lastName": rider["lastName"],
                "sex": rider["sex"],
                "club": rider["club"],
                "clubName": rider["club"],
                "source": "VELOPRESSE",
                "sourceUrl": VELOPRESSE_URL,
                "updatedAt": now,
            },
        ))

    for start in range(0, len(docs), 400):
        batch = db.batch()
        for ref, data in docs[start:start + 400]:
            batch.set(ref, data)
        batch.commit()

    ccp = [r for r in riders if "PLANCOET" in slug(r["club"]).upper()]
    # slug() est en minuscules ; affichage fiable avec comparaison normalisée.
    ccp = [r for r in riders if "plancoet" in slug(r["club"])]

    print(f"\nOK : {len(riders)} engagé(s) écrit(s) dans ffc_engagements.")
    print(f"CC Plancoëtin détectés : {len(ccp)}")
    for r in ccp:
        print(f' - {r["category"]} • {r["firstName"]} {r["lastName"]}')


if __name__ == "__main__":
    main()
