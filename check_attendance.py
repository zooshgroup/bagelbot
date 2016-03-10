#!/usr/bin/env python
import time
from datetime import datetime, timedelta

from config import ATTENDANCE_TIME_LIMIT
from utils import YES, NO, initialize


def check_attendance(store, sc, users=None):
    """Pings all slack users with the email address stored in config.py.

    It asks if they are available for today's meeting, and waits for a pre-determined amount of time.
    If all users respond, or if the time limit is reached, the script exits
    and writes today's upcoming meeting to the store.

    Args:
        store (instance): A persistent, dictionary-like object used to keep information about past/future meetings
        sc (SlackClient): An instance of SlackClient
    """
    start = datetime.now()
    todays_meeting = {'date': start.date(), 'available': [], 'out': []}
    if not users:
        users = store['everyone']
    user_len = len(users)
    messages_sent = {}

    if sc.rtm_connect():
        for user in users:
            print("Pinging {}...".format(user))
            message = sc.api_call(
                "chat.postMessage", channel='@' + user, as_user=True,
                text="Will you be available for today's ({:%m/%d/%Y}) :coffee: and :bagel: meeting? (yes/no)".format(todays_meeting['date'])
            )
            message['user'] = user
            messages_sent[message['channel']] = message

        print("Waiting for responses...")
        while True:
            events = sc.rtm_read()
            for event in events:
                if event['type'] == 'message' and event['channel'] in messages_sent and float(event['ts']) > float(messages_sent[event['channel']]['ts']):
                    lower_txt = event['text'].lower()
                    user = messages_sent[event['channel']]['user']
                    user_responded = False
                    if lower_txt in YES:
                        user_responded = True
                        todays_meeting['available'].append(user)
                        sc.api_call(
                            "chat.postMessage", channel=event['channel'], as_user=True,
                            text="Your presence has been acknowledged! Thank you! :tada:"
                        )
                    elif lower_txt in NO:
                        user_responded = True
                        todays_meeting['out'].append(user)
                        sc.api_call(
                            "chat.postMessage", channel=event['channel'], as_user=True,
                            text="Your absence has been acknowledged! You will be missed! :cry:"
                        )

                    if user_responded:
                        print(u"{} responded with '{}'".format(user, event['text']))
                        # User has responded to bagelbot, don't listen to this channel anymore.
                        messages_sent.pop(event['channel'])

            all_accounted_for = len(todays_meeting['available']) + len(todays_meeting['out']) == user_len
            if datetime.now() > (start + timedelta(seconds=ATTENDANCE_TIME_LIMIT)) or all_accounted_for:
                if not all_accounted_for:
                    # Move any remaining users over to 'out' at the end of the time limit - assuming they aren't available
                    todays_meeting['out'] += [u for u in users if u not in todays_meeting['available'] and u not in todays_meeting['out']]

                print("Finished! These people aren't available today: {}".format(', '.join(todays_meeting['out'])))
                # Store this upcoming meeting under a separate key for use by generate_meeting.py upon actual meeting generation.
                store['upcoming'] = todays_meeting
                break
            else:
                time.sleep(1)
    else:
        print("Connection Failed, invalid token?")


def main(args):
    store, sc = initialize(update_everyone=True)
    try:
        check_attendance(store, sc, users=args.users)
    finally:
        store.close()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Check to see if any Slack members will be missing today's meeting.")
    parser.add_argument('--users', '-u', dest='users', metavar='P', nargs='+', required=False, default=[],
                        help="list of people to check in with (usernames only)")
    main(parser.parse_args())
