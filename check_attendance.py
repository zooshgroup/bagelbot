#!/usr/bin/env python
"""
Bagelbot script for checking for attendance for an upcoming bagelbot meeting.
"""
import logging
import sys
import time
from datetime import datetime, timedelta

from config import ATTENDANCE_TIME_LIMIT
from utils import YES, NO, initialize, nostdout, download_shelve_from_s3, upload_shelve_to_s3

def create_time_limit_string():
    """Create a string according to the time limit in the config
    """
    if (ATTENDANCE_TIME_LIMIT < 60):
        return "%d seconds" % ATTENDANCE_TIME_LIMIT
    if (ATTENDANCE_TIME_LIMIT >= 60 and ATTENDANCE_TIME_LIMIT < 120):  # Singular
        mins = ATTENDANCE_TIME_LIMIT // 60
        secs = ATTENDANCE_TIME_LIMIT % 60
        time_string = "1 minute"
        if secs > 0:
            time_string += " and %d second" % secs
        if secs > 1:
            time_string += "s"
        return time_string
    hours = ATTENDANCE_TIME_LIMIT // (60*60)
    mins = (ATTENDANCE_TIME_LIMIT // 60) - (hours * 60) 
    secs = ATTENDANCE_TIME_LIMIT % 60
    time_string = ""
    if hours > 0:
        time_string = "%d hour" % hours
        if hours > 1:
            time_string += "s"
        if mins > 0 and secs > 0:
            time_string += ", "
        elif mins > 0:
            time_string += " and "
    if mins > 0:
        time_string += "%d minute" % mins
        if mins > 1:
            time_string += "s"
    if secs > 0:
        time_string += " and %d second" % secs
    if secs > 1:
        time_string += "s"
    return time_string

def check_attendance(store, sc, users=None):
    """Pings all slack users with the email address stored in config.py.

    It asks if they are available for today's meeting, and waits for a pre-determined amount of time.
    If all users respond, or if the time limit is reached, the script exits
    and writes today's upcoming meeting to the store.

    Args:
        store (instance): A persistent, dictionary-like object used to keep information about past/future meetings
        sc (SlackClient): An instance of SlackClient
        users (list): A list of users to ping for role call (overrides store['everyone'])
    """
    start = datetime.now()
    todays_meeting = {"date": start.date(), "available": [], "out": []}
    if not users:
        users = store["everyone"]
    user_len = len(users)
    messages_sent = {}
    time_string = create_time_limit_string()

    if sc.rtm_connect():
        for user in users:
            logging.info("Pinging %s...", user)
            message = sc.api_call(
                "chat.postMessage",
                channel="@" + user,
                as_user=True,
                text="Will you be available for today's ({:%Y-%m-%d}) :coffee: shuffle? [yes/no] - Please reply within {}!".format(
                    todays_meeting["date"], time_string
                ),
            )
            message["user"] = user
            messages_sent[message["channel"]] = message

        logging.info("Waiting for responses...")
        while True:
            try:
                events = sc.rtm_read()

                for event in events:
                    logging.debug(event)

                    if (
                        event["type"] == "message"
                        and event["channel"] in messages_sent
                        and float(event["ts"]) > float(messages_sent[event["channel"]]["ts"])
                    ):
                        lower_txt = event["text"].lower().strip()
                        user = messages_sent[event["channel"]]["user"]
                        logging.info(
                            "%s responded with '%s'", user, event["text"].encode("ascii", "ignore")
                        )

                        user_responded = False
                        if lower_txt in YES:
                            user_responded = True
                            todays_meeting["available"].append(user)
                            sc.api_call(
                                "chat.postMessage",
                                channel=event["channel"],
                                as_user=True,
                                text="Your presence has been acknowledged! Thank you! :tada:",
                            )
                        elif lower_txt in NO:
                            user_responded = True
                            todays_meeting["out"].append(user)
                            sc.api_call(
                                "chat.postMessage",
                                channel=event["channel"],
                                as_user=True,
                                text="Your absence has been acknowledged! You will be missed! :cry:",
                            )

                        if user_responded:
                            # User has responded to bagelbot, don't listen to this channel anymore.
                            messages_sent.pop(event["channel"])
            except:
                logging.exception("Something went wrong reading Slack RTM Events.")

            all_accounted_for = (
                len(todays_meeting["available"]) + len(todays_meeting["out"]) == user_len
            )
            if (
                datetime.now() > (start + timedelta(seconds=ATTENDANCE_TIME_LIMIT))
                or all_accounted_for
            ):
                if not all_accounted_for:
                    # Move any remaining users over to 'out' at the end of the time limit - assuming they aren't available
                    todays_meeting["out"] += [
                        u
                        for u in users
                        if u not in todays_meeting["available"] and u not in todays_meeting["out"]
                    ]

                logging.info(
                    "Finished! These people aren't available today: %s",
                    ", ".join(todays_meeting["out"]),
                )
                # Store this upcoming meeting under a separate key for use by generate_meeting.py upon actual meeting generation.
                store["upcoming"] = todays_meeting
                break
            else:
                time.sleep(1)
    else:
        logging.info("Connection Failed, invalid token?")


def main(args):
    """
    Initialize the shelf, possibly sync to s3, then check attendance, close
    the shelf and maybe sync the shelf again.

    Args:
        args (ArgumentParser args): Parsed arguments that impact how the check_attandance runs
    """
    if args.s3_sync:
        download_shelve_from_s3()

    if args.debug:
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format="%(message)s")
    else:
        logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")

    store, sc = initialize(update_everyone=True)
    try:
        check_attendance(store, sc, users=args.users)
    finally:
        store.close()
        if args.s3_sync:
            upload_shelve_to_s3()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Check to see if any Slack members will be missing today's meeting."
    )
    parser.add_argument(
        "--users",
        "-u",
        dest="users",
        metavar="P",
        nargs="+",
        required=False,
        default=[],
        help="list of people to check in with (usernames only)",
    )
    parser.add_argument(
        "--from-cron", "-c", action="store_true", help="Silence all logging statements (stdout)."
    )
    parser.add_argument(
        "--debug", "-d", action="store_true", help="Log all events bagelbot can see."
    )
    parser.add_argument(
        "--s3-sync",
        "-s",
        action="store_true",
        help="Synchronize SHELVE_FILE with AWS S3 before and after checking attendance.",
    )
    parsed_args = parser.parse_args()

    if parsed_args.from_cron:
        with nostdout():
            main(parsed_args)
    else:
        main(parsed_args)
