import os, re, json, hashlib, unicodedata
from datetime import datetime, timezone
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore

TEST_URL="https://velopressecollection.ouest-france.fr/route/engages/38615-pleslin-trigavou-19-septembre-2026-engages-de-course-cycliste.html"
VELOPRESSE_URL=os.getenv("VELOPRESSE_URL",TEST_URL).strip()
CLUB_FILTER=os.getenv("CLUB_FILTER","CC PLANCOETIN").strip()
HEADERS={"User-Agent":"Mozilla/5.0 Chrome/140.0 Safari/537.36","Accept-Language":"fr-FR,fr;q=0.9"}

def clean(v): return re.sub(r"\\s+"," ",v or "").strip()
def ascii_key(v):
    v=unicodedata.normalize("NFD",clean(v))
    v="".join(c for c in v if unicodedata.category(c)!="Mn")
    return re.sub(r"[^A-Z0-9]+","_",v.upper()).strip("_")
def cat(v):
    m=re.search(r"\\b(U7|U9|U11|U13|U15|U17|U19|OPEN|ACCESS)\\b",clean(v).upper())
    return m.group(1) if m else clean(v).upper()

def init_db():
    if firebase_admin._apps: return firestore.client()
    raw=os.getenv("FIREBASE_SERVICE_ACCOUNT","").strip()
    if raw: firebase_admin.initialize_app(credentials.Certificate(json.loads(raw)))
    else: firebase_admin.initialize_app()
    return firestore.client()

def race_info(soup,url):
    title=clean(soup.find("h1").get_text(" ",strip=True) if soup.find("h1") else "")
    months={"janvier":1,"fevrier":2,"février":2,"mars":3,"avril":4,"mai":5,"juin":6,"juillet":7,
            "aout":8,"août":8,"septembre":9,"octobre":10,"novembre":11,"decembre":12,"décembre":12}
    date=""
    m=re.search(r"\\b(\\d{1,2})\\s+([A-Za-zÀ-ÿ]+)\\s+(\\d{4})\\b",title)
    if m and m.group(2).lower() in months:
        date=f"{int(m.group(1)):02d}/{months[m.group(2).lower()]:02d}/{m.group(3)}"
    vid=re.search(r"/engages/(\\d+)-",urlparse(url).path)
    return {"raceName":re.sub(r"\\s+engag[ée]s?.*$","",title,flags=re.I).strip(),
            "raceDate":date,"velopresseId":vid.group(1) if vid else hashlib.sha1(url.encode()).hexdigest()[:12],
            "velopresseUrl":url}

def parse_riders(soup):
    out=[]
    for row in soup.find_all("tr"):
        c=[clean(x.get_text(" ",strip=True)) for x in row.find_all(["td","th"])]
        if len(c)<4: continue
        if len(c)>=5 and c[2].upper() in {"H","F"}: last,first,sex,category,club=c[:5]
        else: last,first,category,club=c[:4]; sex=""
        category=cat(category)
        if not re.fullmatch(r"U\\d{1,2}|OPEN|ACCESS",category) or not last or not first or not club: continue
        out.append({"lastName":last,"firstName":first,"sex":sex.upper(),"category":category,"club":club})
    unique={}
    for r in out:
        unique["|".join(map(ascii_key,[r["lastName"],r["firstName"],r["category"],r["club"]]))]=r
    return list(unique.values())

def doc_id(race,r):
    raw="|".join([race["velopresseId"],r["category"],r["lastName"],r["firstName"],r["club"]])
    return hashlib.sha1(ascii_key(raw).encode()).hexdigest()

def sync(db,race,riders):
    col=db.collection("ffc_engagements"); wanted=set(); batch=db.batch(); writes=0
    for r in riders:
        did=doc_id(race,r); wanted.add(did)
        batch.set(col.document(did),{
            "source":"VELOPRESSE","sourceUrl":race["velopresseUrl"],"velopresseId":race["velopresseId"],
            "raceName":race["raceName"],"raceDate":race["raceDate"],"category":r["category"],
            "firstName":r["firstName"],"lastName":r["lastName"],"runnerName":clean(r["firstName"]+" "+r["lastName"]),
            "sex":r["sex"],"club":r["club"],"engaged":True,"updatedAt":datetime.now(timezone.utc)
        },merge=True); writes+=1
    deletes=0
    for d in col.where("source","==","VELOPRESSE").where("velopresseId","==",race["velopresseId"]).stream():
        if d.id not in wanted: batch.delete(d.reference); deletes+=1
    batch.commit()
    return writes,deletes

def main():
    print("=== SuiviVelo • Synchronisation VéloPresse ===")
    print("URL :",VELOPRESSE_URL)
    r=requests.get(VELOPRESSE_URL,headers=HEADERS,timeout=30); r.raise_for_status()
    soup=BeautifulSoup(r.text,"html.parser"); race=race_info(soup,VELOPRESSE_URL)
    riders=parse_riders(soup)
    if not riders: raise RuntimeError("Aucun engagé détecté : arrêt sans modifier Firebase.")
    club=[x for x in riders if ascii_key(CLUB_FILTER) in ascii_key(x["club"])]
    print("Course :",race["raceName"],"•",race["raceDate"])
    print("Engagés détectés :",len(riders),"•",CLUB_FILTER,":",len(club))
    for x in club: print(" -",x["category"],"•",x["firstName"],x["lastName"])
    writes,deletes=sync(init_db(),race,club)
    print("Firebase : OK • écritures :",writes,"• suppressions obsolètes :",deletes)

if __name__=="__main__": main()
