import os, json, re, hashlib, unicodedata
import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore

VELOPRESSE_URL=os.getenv('VELOPRESSE_URL','https://velopressecollection.ouest-france.fr/route/engages/38615-pleslin-trigavou-19-septembre-2026-engages-de-course-cycliste.html')
CLUB_RECHERCHE=os.getenv('CLUB_RECHERCHE','CC PLANCOETIN')
COURSE_NAME=os.getenv('COURSE_NAME','Pleslin Trigavou')
COURSE_DATE=os.getenv('COURSE_DATE','19/09/2026')
HEADERS={'User-Agent':'Mozilla/5.0 Chrome/140.0 Safari/537.36','Accept-Language':'fr-FR,fr;q=0.9'}

def normaliser(t):
    t=unicodedata.normalize('NFD',str(t or ''))
    return re.sub(r'\s+',' ',''.join(c for c in t if unicodedata.category(c)!='Mn')).upper().strip()

def course_id(): return hashlib.sha256(f'{COURSE_DATE}|{COURSE_NAME}'.encode()).hexdigest()[:24]
def engagement_id(cid,c): return hashlib.sha256(f"{cid}|{normaliser(c['lastName'])}|{normaliser(c['firstName'])}|{normaliser(c['category'])}".encode()).hexdigest()[:32]
def is_cat(v): return bool(re.fullmatch(r'U7|U9|U11|U13|U15|U17|U19|OPEN|ACCESS',normaliser(v)))

def connexion_firebase():
    secret=os.getenv('FIREBASE_SERVICE_ACCOUNT')
    if not secret: raise RuntimeError('Secret FIREBASE_SERVICE_ACCOUNT absent.')
    if not firebase_admin._apps: firebase_admin.initialize_app(credentials.Certificate(json.loads(secret)))
    return firestore.client()

def parse_row(vals):
    vals=[re.sub(r'\s+',' ',v).strip() for v in vals if v and v.strip()]
    if len(vals)<4: return None
    ci=next((i for i in range(2,len(vals)) if is_cat(vals[i])),None)
    if ci is None or ci>=len(vals)-1: return None
    sex=next((normaliser(v) for v in vals[2:ci] if normaliser(v) in ('H','F')),'')
    return {'lastName':vals[0],'firstName':vals[1],'sex':sex,'category':normaliser(vals[ci]),'club':vals[-1]}

def extraire_engages(html):
    soup=BeautifulSoup(html,'html.parser'); out=[]; seen=set()
    for tr in soup.find_all('tr'):
        c=parse_row([x.get_text(' ',strip=True) for x in tr.find_all(['td','th'])])
        if c and normaliser(c['club'])==normaliser(CLUB_RECHERCHE):
            k=(normaliser(c['lastName']),normaliser(c['firstName']),c['category'])
            if k not in seen: seen.add(k); out.append(c)
    if out: return out
    # Fallback pour les articles dont les cellules ne sont pas exposées comme un tableau HTML.
    lines=[x.strip() for x in soup.get_text('\n',strip=True).splitlines() if x.strip()]
    for n in (5,4):
        for i in range(len(lines)-n+1):
            c=parse_row(lines[i:i+n])
            if c and normaliser(c['club'])==normaliser(CLUB_RECHERCHE):
                k=(normaliser(c['lastName']),normaliser(c['firstName']),c['category'])
                if k not in seen: seen.add(k); out.append(c)
    return out

def main():
    print('=== SUIVIVELO - VELOPRESSE ===')
    r=requests.get(VELOPRESSE_URL,headers=HEADERS,timeout=30); r.raise_for_status()
    engages=extraire_engages(r.text)
    print(len(engages),'engagé(s) CCP trouvé(s)')
    if not engages: raise RuntimeError('Aucun engagé CCP trouvé : Firebase laissé intact.')
    db=connexion_firebase(); cid=course_id(); ids=set()
    for c in engages:
        eid=engagement_id(cid,c); ids.add(eid)
        db.collection('ffc_engagements').document(eid).set({
            'courseId':cid,'courseName':COURSE_NAME,'courseDate':COURSE_DATE,
            'firstName':c['firstName'],'lastName':c['lastName'],
            'runnerName':(c['firstName']+' '+c['lastName']).strip(),
            'category':c['category'],'sex':c['sex'],'club':c['club'],
            'source':'VELOPRESSE','sourceUrl':VELOPRESSE_URL,'engaged':True,
            'updatedAt':firestore.SERVER_TIMESTAMP},merge=True)
        print('OK',c['category'],c['firstName'],c['lastName'])
    removed=0
    for doc in db.collection('ffc_engagements').where('courseId','==',cid).stream():
        data=doc.to_dict() or {}
        if data.get('source')=='VELOPRESSE' and doc.id not in ids:
            doc.reference.delete(); removed+=1
    print('Synchronisation terminée -',len(engages),'engagé(s),',removed,'supprimé(s)')

if __name__=='__main__': main()
