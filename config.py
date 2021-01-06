import os
from datetime import timedelta

EMAIL_DOMAIN = "example.com"
SLACK_TOKEN = "yourtoken"
SLACK_CHANNEL = "#general"
SHELVE_FILE = "meetings.shelve"
ATTENDANCE_TIME_LIMIT = 60 * 60
PAIRING_SIZE = 3
GOOGLE_HANGOUT_URL = "https://hangouts.google.com/hangouts/_/"
S3_BUCKET = None
S3_PREFIX = None
FREQUENCY = timedelta(days=0)
TIMEZONE = "US/Central"
ATTENDANCE_TIME = {"hour": 11, "minute": 28, "weekday": 0}
MEETING_TIME = {"hour": 14, "minute": 29, "weekday": 0}

if os.path.exists("config_private.py"):
    # Use config_private for your own personal settings - default to be git ignored.
    # Yup, intentionally using wildcard import to shadow the default values
    from config_private import *
