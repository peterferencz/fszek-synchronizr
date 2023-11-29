# FSZEK syncronizR
Automatically add your borrowings deadlines from the *FSZEK* library to your *Google Calendar*.

# How it works
With a little bit of Python, web scraping and api magic
##### What it does
1. Through HTTPs **requests**, we get a session cookie
2. With the session cookie, we scrape the home page, parsing all the html with **beautifulsoup***
3. We make requisite api calls to **google calendar API**, avoiding duplicate events and already returned books

# Motivation
Although the site provides an *add to calendar* button, You have to 1:log in and 2:manually click each button. Wouldn't be it much simpler, if someone would do it for you?
(I also may or may not have written this purely because I had to pay a late fee)

# How is it ment to be used
You need to set up a google cloud account with a desktop application.
(https://developers.google.com/calendar/api/quickstart/python)[https://developers.google.com/calendar/api/quickstart/python]
It was designed to be run google cloud function infrastructure, but you can run it locally just fine
(https://cloud.google.com/functions/docs/console-quickstart-1st-gen)[https://cloud.google.com/functions/docs/console-quickstart-1st-gen]

# Usage
```md
python synchronizr.py <config.json>
```

# Config.json
the fields of the configuration file provided as the first parameter of the python script
```json
{
    "credentials":{
        "fszek": {
            "barcode": "Your barcode",
            "password": "The password for your fszek account"
        },
        "google":{
            "installed":"The authentication object provided by google cloud console."
        }
    },
    "event":{
        "titleformat": "a rich string. $b for book name, $ll for the full name of the library, $l for the shortened library name. Every other character is treated as regular text",
        "setlocation": "boolean | whether to add the library as the event location",
        "calendar": "The name of the calendar to use. If you don't know, just set it as 'primary'",
        "addlocation": "boolean | weather to set the lcoation field on the event as the library."
    }
}
```