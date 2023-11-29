import requests
import os
import json
import sys
import datetime
from bs4 import BeautifulSoup
from collections import namedtuple
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import re

SESSIONPOSTURL = "https://saman.fszek.hu/WebPac/CorvinaWebSecure?action=patrondata"
BOOKSGETURL = "https://saman.fszek.hu/WebPac/CorvinaWebSecure?action=patrondata"
EPROPERTYNAME = "ADDEDBYFSZEKSYNCHRONIZRUID"

def info(msg):
    print("\x1b[32m[INFO] %s\x1b[0m" % msg)
def warn(msg):
    print("\x1b[33m[WARN] %s\x1b[0m" % msg)
def error(msg, fatal=True):
    print("\x1b[31m[ERROR] %s\x1b[0m" % msg)
    if fatal: exit(1)

if len(sys.argv) < 2:
    warn("Config file not provided, using default 'config.json'")
try:
    configFile = open("config.json" if len(sys.argv) < 2 else sys.argv[1])
    CONFIG = json.loads(configFile.read())
    if "calendar" not in CONFIG["event"]:
        CONFIG["event"]["calendar"] = "primary"
except:
    error("Couldn't open file '%s'" % sys.argv[1])

def getJSessionId(barcode, password):
    res = requests.post(SESSIONPOSTURL, {
        "konyvhosszabbitas_action": "listbooks",
        "patronbarcode": barcode,
        "patronpassword": password,
        "Submit": "Bejelentkezés"
    })
    
    if(res.status_code != 200):
        error("Couldn't log in, chechk if credentials are correct!")

    return res.cookies['JSESSIONID']

def getCalendarService():
    SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
    TOEKNPATH = "token.json"

    creds = None

    if os.path.exists(TOEKNPATH):
        creds = Credentials.from_authorized_user_file(TOEKNPATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            TEMPFILENAME = "weneedtocreatethis.json"
            with open(TEMPFILENAME, 'w') as f:
                f.write(json.dumps(CONFIG["credentials"]["google"]))
            #TODO google only makes it easy, to load it from a file smh
            flow = InstalledAppFlow.from_client_secrets_file(TEMPFILENAME, SCOPES)
            os.remove(TEMPFILENAME)
            creds = flow.run_local_server(port=0)
        with open(TOEKNPATH, 'w') as token:
            token.write(creds.to_json())
    
    if not creds or not creds.valid:
        error("Couldn't authenticate google account, check if ")
    
    return build('calendar', 'v3', credentials=creds)


def getShortenedLibraryName(fullname):
    if(fullname == "Központi Könyvtár"): return "KK"
    fullname = fullname.strip()
    s = fullname.split(', ')
    if(len(s) > 1): fullname = s[1]
    return fullname[0:fullname.rindex(' ')]

def addEvent(service, book):
    event = {
        'summary': str(CONFIG["event"]["titleformat"])
            .replace("$b", book["name"])
            .replace("$ll", book["library"])
            .replace("$l", getShortenedLibraryName(book["library"])),
        'location': book["library"] if CONFIG["event"]["addlocation"] else "",
        'description': 'Return your book',
        'start': {
            'date': book["date"],
            'timeZone': 'Europe/Budapest',
        },
        'end': {
            'date': book["date"],
            'timeZone': 'Europe/Budapest',
        },
        'transparency': 'transparent',
        'extendedProperties': {
            'private': {
                #To only edit our own events
                EPROPERTYNAME: book["uid"]
            }
        }
        # 'reminders': {
        #     'useDefault': False,
        #     'overrides': [
        #         {'method': 'email', 'minutes': 24 * 60},
        #         {'method': 'popup', 'minutes': 10},
        #   ],
        # }
    }
    service.events().insert(calendarId=CONFIG["event"]["calendar"], body=event).execute()

def getBooks():
    info("Getting jsessionid")
    sessionid = getJSessionId(CONFIG["credentials"]["fszek"]["barcode"], CONFIG["credentials"]["fszek"]["password"])
    info("Fetching books")
    res = requests.get(BOOKSGETURL, cookies={
        "JSESSIONID":sessionid,
    }, headers={
        "Accept-Encoding":"utf-8"
    })
    html = BeautifulSoup(res.text, "html.parser")
    books = []
    for library in html.select("#tab_libraries #patron_libraries > div"):
        libraryName = library.select_one("span.library_data").text
        #http://www.google.com/calendar/event?action=TEMPLATE&text=Kölcsönzés lejár&dates=20231207/20231208&details=Szerző: Camus, Albert, Cím: Boldog halál%0a?action=advancedsearchpage&location=&trp=false&sprop=&sprop=name:
        for book in library.select("a[href^=\"http://www.google.com/calendar/event\"]"):
            re_author = re.search("Szerző: .*\,", book["href"])
            author = book["href"][re_author.start()+8:re_author.end()-1]
            re_title = re.search("Cím: .*\%", book["href"])
            title = book["href"][re_title.start()+5:re_title.end()-1]
            re_date = re.search("&dates=.*?\&", book["href"])
            d = book["href"][re_date.start()+7:re_date.end()-1].split("/")[0]
            books.append({
                "name": title,
                "author": author,
                "library": libraryName,
                "date": d[0:4] + '-' + d[4:6] + '-' + d[6:8],
                "uid": libraryName[0:4] + author[0:10] + title[0:10]
            })
    return books

#TODO could improve with partial response (https://gsuite-developers.googleblog.com/2017/03/using-field-masks-with-google-apis-for_31.html)
def addBooks(service, books):
    autoEvents = [
        {
            "id": event["id"],
            "property":event["extendedProperties"]["private"][EPROPERTYNAME]
        } for event in 
        service.events().list(
            calendarId=CONFIG["event"]["calendar"],
            timeMin=datetime.datetime.utcnow().isoformat() + "Z",
            maxResults=30,
            singleEvents=True,
            orderBy="startTime",
        ).execute().get("items", [])
        if "extendedProperties" in event and "private" in event["extendedProperties"] and EPROPERTYNAME in event["extendedProperties"]["private"]
    ]

    for book in books:
        if any(event["property"] == book["uid"] for event in autoEvents):
            info("Skipping id %s" % book["uid"])
            autoEvents = [event for event in autoEvents if event["property"] != book["uid"]]
            continue

        info("Adding %s by %s with token %s" % (book["name"], book["author"], book["uid"]))
        addEvent(service, book)
    
    for property in autoEvents:
        info("Deleting event with token %s" % property["property"])
        service.events().delete(calendarId=CONFIG["event"]["calendar"], eventId=property["id"]).execute()
    

def _main_():
    info("Starting synchronizer")
    books = getBooks()
    service = getCalendarService()
    addBooks(service, books)

_main_()