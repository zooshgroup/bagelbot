#!/usr/bin/env python
"""
Bagelbot script that is designed to run constantly and check to see if role call should be ran and then if a meeting should be generated.
"""
import logging
import sys
import time
from datetime import datetime

from pytz import timezone

from config import ATTENDANCE_TIME, FREQUENCY, MEETING_TIME, S3_BUCKET, TIMEZONE
from check_attendance import check_attendance
from generate_meeting import create_meetings
from utils import (
    initialize,
    download_shelve_from_s3,
    update_everyone_from_slack,
    upload_shelve_to_s3,
)

logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")
DATE_FMT = "%m/%d/%Y"


def main():
    """
    Initialize the shelf, possibly sync to s3, then check attendance, close
    the shelf and maybe sync the shelf again.

    Args:
        args (ArgumentParser args): Parsed arguments that impact how the check_attandance runs
    """
    if S3_BUCKET:
        download_shelve_from_s3()

    tz = timezone(TIMEZONE)
    store, sc = initialize(update_everyone=True)

    try:
        while True:
            # Get current time, and date of our last meeting
            now = datetime.now(tz)
            logging.info("It's now %s,", now.strftime(DATE_FMT))
            last_meeting = store["history"][-1]
            logging.info("and the last meeting was on %s.", last_meeting["date"].strftime(DATE_FMT))

            # Determine if it's time to check attendance
            attendance_time = all(
                [
                    (now.date() - last_meeting["date"]) >= FREQUENCY,
                    now.hour == ATTENDANCE_TIME["hour"],
                    now.minute == ATTENDANCE_TIME["minute"],
                    now.weekday() == ATTENDANCE_TIME["weekday"],
                ]
            )
            logging.info("Is it attendance checking time? %s", attendance_time)

            # Determine if it's time for a new meeting
            meeting_time = all(
                [
                    (now.date() - last_meeting["date"]) >= FREQUENCY,
                    now.hour == MEETING_TIME["hour"],
                    now.minute == MEETING_TIME["minute"],
                    now.weekday() == MEETING_TIME["weekday"],
                ]
            )
            logging.info("Is it meeting generating time? %s", meeting_time)

            sync = False
            if attendance_time:
                logging.info("Gonna check that attendance!")
                update_everyone_from_slack(store, sc)
                check_attendance(store, sc)
                sync = True
            elif meeting_time:
                logging.info("Let's try to generate a meeting!")
                update_everyone_from_slack(store, sc)
                max_attempts, attempt = 100, 1
                success = False
                while not success:
                    success = create_meetings(
                        store, sc, force_create=True, any_pair=attempt > max_attempts
                    )
                    attempt += 1
                sync = True

            if sync:
                logging.info("Syncing to local storage.")
                store.sync()
                if S3_BUCKET:
                    logging.info("Uploading to s3.")
                    upload_shelve_to_s3()

            # Go to sleep for a minute and check again
            logging.info("Going to sleep for a minute.")
            time.sleep(60)
    finally:
        store.close()


if __name__ == "__main__":
    main()
