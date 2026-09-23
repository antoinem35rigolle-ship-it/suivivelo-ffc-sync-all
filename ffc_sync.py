import hashlib
import json
import os
import re
import unicodedata
from datetime import date as date_type, datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse

import firebase_admin
import requests
from bs4 import BeautifulSoup
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter

BASE_URL = "https://velopressecollection.ouest-france.fr"
INDEX_URLS = (
    f"{BASE_URL}/route/engages/",
    f"{BASE_URL}/cyclo-cross/engages/",
)
RESULT_INDEX_URLS = (
    f"{BASE_URL}/route/classements/",
    f"{BASE_URL}/cyclo-cross/classements/",
)
MANUAL_URL = os.environ.get("VELOPRESSE_URL", "").strip()
MAX_ARTICLES = max(1, int(os.environ.get("MAX_ARTICLES", "80")))
PAST_GRACE_DAYS = max(0, int(os.environ.get("PAST_GRACE_DAYS", "1")))
# Un nettoyage complet lit de nombreuses fiches historiques. À lancer
# ponctuellement avec CLEANUP_OLD_DOCS=1, jamais à chaque synchronisation.
CLEANUP_OLD_DOCS = os.environ.get("CLEANUP_OLD_DOCS", "0") == "1"

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

DATE_PATTERN = re.compile(
    r"(.+?)\s+(\d{1,2})\s+"
    r"(janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[ée]cembre)"
    r"\s+(\d{4})",
    flags=re.I,
)


def clean(value):
    return re.sub(r"\s+", " ", (value or "")).strip()


def slug(value):
    value = unicodedata.normalize("NFD", clean(value))
    value = "".join(c for c in value if unicodedata.category(c) != "Mn")
    return re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()


def parse_french_date(value):
    match = DATE_PATTERN.search(clean(value))
    if not match:
        return None
    try:
        return date_type(
            int(match.group(4)),
            MONTHS[match.group(3).lower()],
            int(match.group(2)),
        )
    except (KeyError, ValueError):
        return None


def firebase():
    raw = os.environ.get("FIREBASE_SERVICE_ACCOUNT", "").strip()
    if not raw:
        raise RuntimeError("Secret FIREBASE_SERVICE_ACCOUNT absent.")
    info = json.loads(raw)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(info))
    return firestore.client()


def get_soup(session, url):
    response = session.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def is_velopresse_engagement_url(url):
    parsed = urlparse(url)
    return (
        parsed.netloc == "velopressecollection.ouest-france.fr"
        and "/engages/" in parsed.path
        and parsed.path.endswith(".html")
        and not re.search(r"/page-\d+\.html$", parsed.path, flags=re.I)
    )


def is_velopresse_result_url(url):
    parsed = urlparse(url)
    return (
        parsed.netloc == "velopressecollection.ouest-france.fr"
        and "/classements/" in parsed.path
        and parsed.path.endswith(".html")
        and not re.search(r"/page-\d+\.html$", parsed.path, flags=re.I)
    )


def discover_article_urls(session):
    """Trouve les fiches récentes sur les index Route et Cyclo-cross."""
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=PAST_GRACE_DAYS)
    discovered = []
    seen = set()
    for index_url in INDEX_URLS:
        print("Index      :", index_url)
        soup = get_soup(session, index_url)
        for anchor in soup.find_all("a", href=True):
            url = urljoin(index_url, anchor.get("href", "")).split("#", 1)[0]
            if url in seen or not is_velopresse_engagement_url(url):
                continue
            label = clean(anchor.get_text(" ", strip=True))
            race_date = parse_french_date(label) or parse_french_date(url.replace("-", " "))
            if race_date is not None and race_date < cutoff:
                continue
            seen.add(url)
            discovered.append(url)
            if len(discovered) >= MAX_ARTICLES:
                return discovered
    return discovered


def discover_result_urls(session):
    """Trouve les classements récemment publiés Route et Cyclo-cross."""
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=14)
    discovered = []
    seen = set()
    for index_url in RESULT_INDEX_URLS:
        print("Résultats  :", index_url)
        soup = get_soup(session, index_url)
        for anchor in soup.find_all("a", href=True):
            url = urljoin(index_url, anchor.get("href", "")).split("#", 1)[0]
            if url in seen or not is_velopresse_result_url(url):
                continue
            label = clean(anchor.get_text(" ", strip=True))
            race_date = parse_french_date(label) or parse_french_date(url.replace("-", " "))
            if race_date is not None and race_date < cutoff:
                continue
            seen.add(url)
            discovered.append(url)
            if len(discovered) >= MAX_ARTICLES:
                return discovered
    return discovered


def extract_course_info(soup, source_url):
    h1 = soup.find("h1")
    if h1:
        raw_title = clean(h1.get_text(" ", strip=True))
    elif soup.title:
        raw_title = clean(soup.title.get_text(" ", strip=True))
    else:
        raise RuntimeError("Titre VéloPresse introuvable.")

    match = DATE_PATTERN.search(raw_title)
    if not match:
        raise RuntimeError("Date de course introuvable dans le titre VéloPresse.")
    place = clean(match.group(1))
    race_date = date_type(
        int(match.group(4)), MONTHS[match.group(3).lower()], int(match.group(2))
    )
    course_title = re.sub(
        r"\s+(engag[ée]e?s?|partant(?:e)?s?|liste\s+des\s+engag[ée]e?s?|classements?|r[ée]sultats?).*$",
        "", raw_title, flags=re.I,
    ).strip()
    discipline = "CYCLOCROSS" if "/cyclo-cross/" in source_url.lower() else "ROUTE"
    return course_title, place, race_date, discipline


def normalize_category(value):
    category = clean(value).upper().replace("É", "E")
    match = re.search(r"\bU\s*(7|9|11|13|15|17|19|23)\b", category)
    if match:
        return "U" + match.group(1)
    for expected in ("OPEN", "ACCESS", "ELITE", "ESPOIR", "SENIOR", "MASTER"):
        if expected in category:
            return expected
    return ""


def parse_rows(soup):
    riders = []

    def add_parts(parts):
        parts = [clean(part) for part in parts if clean(part)]
        if len(parts) < 4:
            return
        if len(parts) >= 5 and parts[2].upper() in {"H", "F", "M"}:
            last_name, first_name, sex, raw_category, club = parts[:5]
        else:
            last_name, first_name = parts[0], parts[1]
            sex = ""
            raw_category, club = parts[-2], parts[-1]
        category = normalize_category(raw_category)
        if not category or not last_name or not first_name or not club:
            return
        riders.append({
            "lastName": last_name,
            "firstName": first_name,
            "sex": sex.upper(),
            "category": category,
            "club": club,
        })

    for row in soup.find_all("tr"):
        add_parts([cell.get_text(" ", strip=True) for cell in row.find_all(["td", "th"])])
    if not riders:
        for line in soup.get_text("\n", strip=True).splitlines():
            if "|" in line:
                add_parts(line.split("|"))

    unique = {}
    for rider in riders:
        key = "|".join((
            slug(rider["lastName"]), slug(rider["firstName"]),
            slug(rider["category"]), slug(rider["club"]),
        ))
        unique[key] = rider
    return list(unique.values())


def parse_result_rows(soup):
    """Lit place, nom, prénom, club en conservant la section U7/U9/U11…"""
    results = []
    current_category = ""
    for element in soup.find_all(["h2", "h3", "h4", "h5", "caption", "tr"]):
        if element.name != "tr":
            detected = normalize_category(element.get_text(" ", strip=True))
            if detected:
                current_category = detected
            continue

        parts = [clean(cell.get_text(" ", strip=True))
                 for cell in element.find_all(["td", "th"])]
        parts = [part for part in parts if part]
        if len(parts) < 4:
            continue
        rank_match = re.search(r"\d+", parts[0])
        if not rank_match:
            row_category = normalize_category(" ".join(parts))
            if row_category:
                current_category = row_category
            continue
        rank = int(rank_match.group(0))
        if rank <= 0:
            continue

        row_category = ""
        for part in parts:
            row_category = normalize_category(part)
            if row_category:
                break
        category = row_category or current_category
        if not category:
            continue

        # Deux présentations sont utilisées par VéloPresse :
        #   Pleslin : place | NOM | Prénom | Club
        #   Landivy : place | NOM Prénom | Club | U11-1
        # Certaines pages ajoutent aussi la catégorie après quatre colonnes.
        category_at_end = normalize_category(parts[-1])
        if category_at_end:
            club = parts[-2]
            name_cells = parts[1:-2]
            if len(name_cells) >= 2:
                last_name = name_cells[0]
                first_name = " ".join(name_cells[1:])
            elif len(name_cells) == 1:
                full_name = name_cells[0].split()
                if len(full_name) < 2:
                    continue
                last_name = " ".join(full_name[:-1])
                first_name = full_name[-1]
            else:
                continue
        else:
            last_name, first_name = parts[1], parts[2]
            club = parts[-1]
        if not last_name or not first_name or not club:
            continue
        results.append({
            "rank": rank,
            "lastName": last_name,
            "firstName": first_name,
            "category": category,
            "club": club,
        })

    unique = {}
    for result in results:
        key = "|".join((
            result["category"], slug(result["lastName"]),
            slug(result["firstName"]), slug(result["club"]),
        ))
        unique[key] = result
    return list(unique.values())


def replace_course_documents(db, source_url, title, place, race_date, discipline, riders):
    collection = db.collection("ffc_engagements")
    old = list(
        collection.where(
            filter=FieldFilter("sourceUrl", "==", source_url)
        ).stream()
    )
    existing = {document.id: document for document in old}

    now = datetime.now(timezone.utc)
    date_text = race_date.strftime("%d/%m/%Y")
    documents = []
    active_ids = set()
    for rider in riders:
        runner_name = clean(f'{rider["firstName"]} {rider["lastName"]}')
        identity = "|".join((
            source_url, rider["category"], rider["lastName"],
            rider["firstName"], rider["club"],
        ))
        document_id = hashlib.sha1(identity.encode("utf-8")).hexdigest()
        active_ids.add(document_id)
        data = {
            "title": title,
            "courseTitle": title,
            "date": date_text,
            "courseDate": date_text,
            "courseDateIso": race_date.isoformat(),
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
            "sourceUrl": source_url,
        }
        previous = existing.get(document_id)
        # Les horodatages ne doivent pas provoquer une réécriture à chaque passage.
        if previous is None or any(
            (previous.to_dict() or {}).get(key) != value for key, value in data.items()
        ):
            data["updatedAt"] = now
            documents.append((collection.document(document_id), data))

    stale = [doc for doc_id, doc in existing.items() if doc_id not in active_ids]

    for start in range(0, len(documents), 400):
        batch = db.batch()
        for reference, data in documents[start:start + 400]:
            # Conserve les classements éventuels sur la fiche d'engagement.
            batch.set(reference, data, merge=True)
        batch.commit()
    for start in range(0, len(stale), 400):
        batch = db.batch()
        for document in stale[start:start + 400]:
            batch.delete(document.reference)
        batch.commit()
    print(f"Engagés : {len(documents)} modifiés, {len(stale)} retirés, "
          f"{len(riders) - len(documents)} inchangés")


def sync_article(session, db, source_url):
    soup = get_soup(session, source_url)
    title, place, race_date, discipline = extract_course_info(soup, source_url)
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=PAST_GRACE_DAYS)
    if not MANUAL_URL and race_date < cutoff:
        return 0, 0, "ancienne"
    riders = parse_rows(soup)
    if not riders:
        return 0, 0, "aucun engagé détecté"
    replace_course_documents(db, source_url, title, place, race_date, discipline, riders)
    ccp = [rider for rider in riders if "plancoet" in slug(rider["club"])]
    print(
        f"OK • {race_date.strftime('%d/%m/%Y')} • {title} • "
        f"{len(riders)} engagés • {len(ccp)} CCP"
    )
    return len(riders), len(ccp), "ok"


def sync_result_article(session, db, source_url):
    soup = get_soup(session, source_url)
    title, place, race_date, discipline = extract_course_info(soup, source_url)
    results = parse_result_rows(soup)
    if not results:
        return 0, 0, "aucun classement détecté"

    date_iso = race_date.isoformat()
    date_text = race_date.strftime("%d/%m/%Y")
    existing = list(
        db.collection("ffc_engagements").where(
            filter=FieldFilter("courseDateIso", "==", date_iso)
        ).stream()
    )
    existing_by_path = {document.reference.path: document.to_dict() or {}
                        for document in existing}
    previous_result_documents = [
        document for document in existing
        if (document.to_dict() or {}).get("resultSourceUrl") == source_url
    ]
    by_runner = {}
    for document in existing:
        values = document.to_dict() or {}
        key = "|".join((
            normalize_category(values.get("category")),
            slug(values.get("lastName")), slug(values.get("firstName")),
        ))
        by_runner.setdefault(key, []).append(document)

    participants_by_category = {}
    for result in results:
        category = result["category"]
        participants_by_category[category] = participants_by_category.get(category, 0) + 1

    now = datetime.now(timezone.utc)
    writes = []
    active_paths = set()
    matched = 0
    for result in results:
        key = "|".join((
            result["category"], slug(result["lastName"]), slug(result["firstName"]),
        ))
        candidates = by_runner.get(key, [])
        reference = candidates[0].reference if candidates else None
        if reference is not None:
            matched += 1
        else:
            identity = "result|" + "|".join((
                source_url, result["category"], result["lastName"],
                result["firstName"], result["club"],
            ))
            document_id = hashlib.sha1(identity.encode("utf-8")).hexdigest()
            reference = db.collection("ffc_engagements").document(document_id)

        runner_name = clean(f'{result["firstName"]} {result["lastName"]}')
        active_paths.add(reference.path)
        data = {
            "title": title, "courseTitle": title,
            "date": date_text, "courseDate": date_text,
            "courseDateIso": date_iso, "place": place,
            "discipline": discipline, "category": result["category"],
            "runnerName": runner_name,
            "firstName": result["firstName"], "lastName": result["lastName"],
            "club": result["club"], "clubName": result["club"],
            "rank": result["rank"],
            "participants": participants_by_category[result["category"]],
            "resultSource": "VELOPRESS", "resultSourceUrl": source_url,
            "source": "VELOPRESSE",
        }
        previous = existing_by_path.get(reference.path, {})
        if any(previous.get(field) != value for field, value in data.items()):
            data["resultUpdatedAt"] = now
            data["updatedAt"] = now
            writes.append((reference, data))

    for start in range(0, len(writes), 400):
        batch = db.batch()
        for reference, data in writes[start:start + 400]:
            batch.set(reference, data, merge=True)
        batch.commit()

    # Retire les anciennes lignes mal interprétées lorsqu'une page change de
    # format ou lorsque le parseur est amélioré, sans toucher aux autres courses.
    stale = [document for document in previous_result_documents
             if document.reference.path not in active_paths]
    for start in range(0, len(stale), 400):
        batch = db.batch()
        for document in stale[start:start + 400]:
            batch.delete(document.reference)
        batch.commit()

    ccp = sum(1 for result in results if "plancoet" in slug(result["club"]))
    print(
        f"RÉSULTATS • {date_text} • {title} • {len(results)} classés • "
        f"{ccp} CCP • {matched} engagement(s) enrichi(s)"
    )
    return len(results), ccp, "ok"


def cleanup_old_documents(db):
    """Supprime les listes devenues anciennes pour garder la collection légère."""
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=PAST_GRACE_DAYS)
    collection = db.collection("ffc_engagements")
    obsolete = []
    for document in collection.where(
        filter=FieldFilter("courseDateIso", "<", cutoff.isoformat())
    ).stream():
        values = document.to_dict() or {}
        if int(values.get("rank") or 0) > 0:
            continue
        raw = clean(values.get("courseDateIso"))
        try:
            race_date = date_type.fromisoformat(raw)
        except (TypeError, ValueError):
            legacy = clean(values.get("courseDate") or values.get("date"))
            try:
                race_date = datetime.strptime(legacy, "%d/%m/%Y").date()
            except (TypeError, ValueError):
                continue
        if race_date < cutoff:
            obsolete.append(document)
    for start in range(0, len(obsolete), 400):
        batch = db.batch()
        for document in obsolete[start:start + 400]:
            batch.delete(document.reference)
        batch.commit()
    return len(obsolete)


def main():
    print("=== SuiviVélo • VéloPresse -> Firebase ===")
    session = requests.Session()
    db = firebase()
    if MANUAL_URL:
        engagement_urls = [MANUAL_URL] if is_velopresse_engagement_url(MANUAL_URL) else []
        result_urls = [MANUAL_URL] if is_velopresse_result_url(MANUAL_URL) else []
    else:
        engagement_urls = discover_article_urls(session)
        result_urls = discover_result_urls(session)

    if not engagement_urls and not result_urls:
        removed = cleanup_old_documents(db) if CLEANUP_OLD_DOCS and not MANUAL_URL else 0
        print("Aucune nouvelle fiche d'engagés ou de résultats trouvée sur VéloPresse.")
        print("Anciens docs supprimés :", removed)
        return
    print("Fiches engagés trouvées  :", len(engagement_urls))
    print("Fiches résultats trouvées:", len(result_urls))

    synced = total_riders = total_ccp = 0
    errors = []
    for index, source_url in enumerate(engagement_urls, start=1):
        print(f"\n[ENGAGÉS {index}/{len(engagement_urls)}] {source_url}")
        try:
            riders, ccp, status = sync_article(session, db, source_url)
            if status == "ok":
                synced += 1
                total_riders += riders
                total_ccp += ccp
            else:
                print("Ignorée    :", status)
        except Exception as error:
            message = f"{source_url} -> {type(error).__name__}: {error}"
            errors.append(message)
            print("ERREUR     :", message)

    result_synced = total_results = result_ccp = 0
    for index, source_url in enumerate(result_urls, start=1):
        print(f"\n[RÉSULTATS {index}/{len(result_urls)}] {source_url}")
        try:
            riders, ccp, status = sync_result_article(session, db, source_url)
            if status == "ok":
                result_synced += 1
                total_results += riders
                result_ccp += ccp
            else:
                print("Ignorée    :", status)
        except Exception as error:
            message = f"{source_url} -> {type(error).__name__}: {error}"
            errors.append(message)
            print("ERREUR     :", message)

    removed = cleanup_old_documents(db) if CLEANUP_OLD_DOCS and not MANUAL_URL else 0
    print("\n=== BILAN ===")
    print("Courses synchronisées :", synced)
    print("Engagés écrits         :", total_riders)
    print("Engagés CCP détectés   :", total_ccp)
    print("Classements synchronisés:", result_synced)
    print("Résultats écrits        :", total_results)
    print("Résultats CCP détectés  :", result_ccp)
    print("Anciens docs supprimés :", removed)
    print("Fiches en erreur       :", len(errors))
    if synced == 0 and result_synced == 0:
        raise RuntimeError(
            "Aucun engagé ni résultat n'a pu être synchronisé. " + " | ".join(errors[:5])
        )


if __name__ == "__main__":
    main()
