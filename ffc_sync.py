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


# ============================================================
# CONFIGURATION
# ============================================================

VELOPRESSE_URL = (
    "https://velopressecollection.ouest-france.fr/route/engages/"
    "38615-pleslin-trigavou-19-septembre-2026-engages-de-course-cycliste.html"
)

CLUB_RECHERCHE = "CC PLANCOETIN"

COURSE_NAME = "Pleslin Trigavou"
COURSE_DATE = "19/09/2026"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
}


# ============================================================
# OUTILS
# ============================================================

def normaliser(texte):
    if not texte:
        return ""

    texte = unicodedata.normalize("NFD", texte)

    texte = "".join(
        c for c in texte
        if unicodedata.category(c) != "Mn"
    )

    return texte.upper().strip()


def creer_id_course():
    brut = f"{COURSE_DATE}|{COURSE_NAME}"

    return hashlib.sha256(
        brut.encode("utf-8")
    ).hexdigest()[:24]


def creer_id_engagement(course_id, nom, prenom, categorie):
    brut = (
        f"{course_id}|"
        f"{normaliser(nom)}|"
        f"{normaliser(prenom)}|"
        f"{normaliser(categorie)}"
    )

    return hashlib.sha256(
        brut.encode("utf-8")
    ).hexdigest()[:32]


# ============================================================
# FIREBASE
# ============================================================

def connexion_firebase():

    secret = os.environ.get("FIREBASE_SERVICE_ACCOUNT")

    if not secret:
        raise RuntimeError(
            "Le secret FIREBASE_SERVICE_ACCOUNT est absent."
        )

    informations = json.loads(secret)

    cred = credentials.Certificate(informations)

    firebase_admin.initialize_app(cred)

    return firestore.client()


# ============================================================
# VELOPRESSE
# ============================================================

def recuperer_page():

    print("Téléchargement VéloPresse...")

    response = requests.get(
        VELOPRESSE_URL,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    print(
        "Page récupérée :",
        response.status_code,
        "-",
        len(response.content),
        "octets"
    )

    return response.text


def extraire_engages(html):

    soup = BeautifulSoup(html, "html.parser")

    texte = soup.get_text("\n", strip=True)

    lignes = [
        ligne.strip()
        for ligne in texte.splitlines()
        if ligne.strip()
    ]

    engages = []

    # Les lignes VéloPresse ont cette forme :
    #
    # NOM | Prénom | H/F | U11 | CLUB
    #
    # Certaines catégories n'ont pas toujours la colonne sexe.
    pattern_5 = re.compile(
        r"^\s*(.*?)\s*\|\s*"
        r"(.*?)\s*\|\s*"
        r"([HF])\s*\|\s*"
        r"(U7|U9|U11|U13|U15|U17)\s*\|\s*"
        r"(.*?)\s*$",
        re.IGNORECASE
    )

    pattern_4 = re.compile(
        r"^\s*(.*?)\s*\|\s*"
        r"(.*?)\s*\|\s*"
        r"(U7|U9|U11|U13|U15|U17)\s*\|\s*"
        r"(.*?)\s*$",
        re.IGNORECASE
    )

    for ligne in lignes:

        match = pattern_5.match(ligne)

        if match:

            nom = match.group(1).strip()
            prenom = match.group(2).strip()
            sexe = match.group(3).upper()
            categorie = match.group(4).upper()
            club = match.group(5).strip()

        else:

            match = pattern_4.match(ligne)

            if not match:
                continue

            nom = match.group(1).strip()
            prenom = match.group(2).strip()
            sexe = ""
            categorie = match.group(3).upper()
            club = match.group(4).strip()

        if normaliser(club) != normaliser(CLUB_RECHERCHE):
            continue

        engages.append({
            "lastName": nom,
            "firstName": prenom,
            "sex": sexe,
            "category": categorie,
            "club": club
        })

    return engages


# ============================================================
# FIRESTORE
# ============================================================

def enregistrer_engages(db, engages):

    course_id = creer_id_course()

    print()
    print("Course :", COURSE_NAME)
    print("Date :", COURSE_DATE)
    print("ID course :", course_id)
    print()

    nouveaux_ids = set()

    for coureur in engages:

        engagement_id = creer_id_engagement(
            course_id,
            coureur["lastName"],
            coureur["firstName"],
            coureur["category"]
        )

        nouveaux_ids.add(engagement_id)

        document = {
            "courseId": course_id,

            "courseName": COURSE_NAME,
            "courseDate": COURSE_DATE,

            "firstName": coureur["firstName"],
            "lastName": coureur["lastName"],

            "runnerName": (
                coureur["firstName"]
                + " "
                + coureur["lastName"]
            ).strip(),

            "category": coureur["category"],
            "sex": coureur["sex"],
            "club": coureur["club"],

            "source": "VELOPRESSE",
            "sourceUrl": VELOPRESSE_URL,

            "engaged": True,

            "updatedAt": firestore.SERVER_TIMESTAMP
        }

        db.collection(
            "ffc_engagements"
        ).document(
            engagement_id
        ).set(
            document,
            merge=True
        )

        print(
            "OK :",
            coureur["category"],
            "-",
            coureur["firstName"],
            coureur["lastName"]
        )

    # --------------------------------------------------------
    # SUPPRESSION DES ENGAGEMENTS VELOPRESSE DEVENUS OBSOLETES
    # --------------------------------------------------------

    anciens = (
        db.collection("ffc_engagements")
        .where("courseId", "==", course_id)
        .stream()
    )

    supprimes = 0

    for document in anciens:

        data = document.to_dict()

        if data.get("source") != "VELOPRESSE":
            continue

        if document.id not in nouveaux_ids:

            document.reference.delete()

            supprimes += 1

            print(
                "SUPPRIMÉ :",
                data.get("runnerName", document.id)
            )

    return course_id, supprimes


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("==========================================")
    print(" SUIVIVELO - SYNCHRONISATION VELOPRESSE")
    print("==========================================")
    print()

    db = connexion_firebase()

    html = recuperer_page()

    engages = extraire_engages(html)

    print()
    print(
        len(engages),
        "engagé(s) trouvé(s) pour",
        CLUB_RECHERCHE
    )
    print()

    if not engages:

        raise RuntimeError(
            "Aucun engagé CC PLANCOETIN trouvé. "
            "La synchronisation est annulée."
        )

    for coureur in engages:

        print(
            coureur["category"],
            "-",
            coureur["firstName"],
            coureur["lastName"]
        )

    course_id, supprimes = enregistrer_engages(
        db,
        engages
    )

    print()
    print("==========================================")
    print(" SYNCHRONISATION TERMINÉE")
    print("==========================================")

    print(
        "Course :",
        COURSE_NAME
    )

    print(
        "Engagés CCP :",
        len(engages)
    )

    print(
        "Engagements supprimés :",
        supprimes
    )

    print(
        "Collection Firebase : ffc_engagements"
    )

    print(
        "Course ID :",
        course_id
    )


if __name__ == "__main__":
    main()
