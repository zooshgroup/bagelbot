#!/usr/bin/env python
"""
Bagelbot script for generating an upcoming bagelbot meeting.
"""

from __future__ import print_function

import random
import sys
from datetime import date
from uuid import uuid4

from six.moves import input

from config import GOOGLE_HANGOUT_URL, PAIRING_SIZE, SLACK_CHANNEL
from utils import YES, NO, initialize, nostdout, download_shelve_from_s3, upload_shelve_to_s3


def get_google_hangout_url():
    return "{}{}?authuser=0".format(GOOGLE_HANGOUT_URL, uuid4())


def create_meetings(store,
                    sc,
                    size=PAIRING_SIZE,
                    whos_out=None,
                    pairs=None,
                    force_create=False,
                    any_pair=False):
    """Randomly generates sets of pairs for (usually) 1 on 1 meetings for a Slack team.

    Given the `size`, list of all users and who is out today, it generates a randomized set of people
    to per group to meet and chat. It tries not to redo any groups from the past nCr weeks (experimental).

    Args:
        store (instance): A persistent, dictionary-like object used to keep information about past/future meetings
        sc (SlackClient): An instance of SlackClient
        size (int): Pair size - defaulted to PAIRING_SIZE in config.py
        whos_out (list): List of slack users who aren't available for the meeting
        pairs (list): List of slack users explictly pair up (elements of list are in the form of 'username+username')
        force_create (Optional[bool]): If True, generate the meeting and write it to storage without asking if it should.
        any_pair (Optional[bool]): If True, generate any pairing - regardless if it's happened in the past or not

    Returns:
        bool: True if successful, False otherwise.
    """
    if whos_out is None:
        whos_out = []
    if pairs is None:
        pairs = []

    todays_meeting = {'date': date.today(), 'attendees': []}
    found_upcoming = False
    if store.get('upcoming') and store['upcoming']['date'] == todays_meeting['date']:
        print("Found upcoming meeting, using appending whoever is listed as out from it.")
        whos_out = whos_out + store['upcoming']['out']
        found_upcoming = True

    names = [n for n in store['everyone'] if n not in whos_out]
    max_pair_size = size

    # == Handle Explicit Pairs ==
    for _, explicit_pair in enumerate(pairs):
        local_names = names[:]
        pairing = []

        try:
            members = explicit_pair.split('+')
            for member in members:
                local_names.remove(member)
                pairing.append(member)
        except:
            sys.exit(
                "ERROR: The following explicit pair was either malformed, contained invalid user names, or has members listed as being out: {}".
                format(explicit_pair))

        # Store difference of names (remaining people to pair)
        max_pair_size = max(max_pair_size, len(pairing))
        names = [n for n in names if n in local_names]
        todays_meeting['attendees'].append(frozenset(pairing))

    # == Set up Random Pairing Numbers ==
    names_len = len(names)
    if names_len < size:
        if found_upcoming:
            del store['upcoming']
        sc.api_call(
            "chat.postMessage",
            channel=SLACK_CHANNEL,
            as_user=True,
            text="Today's :coffee: and :bagel: has been canceled - not enough people are available!"
        )
        sys.exit("ERROR: Not enough people to have a meeting, canceling request.")

    number_of_pairings = names_len // size
    out_remainder = names_len % size
    max_pair_size = max(max_pair_size, names_len + out_remainder + 1)
    print("Going to generate {} pairs for today's meeting...".format(number_of_pairings))
    # Get the nCr of meetings and try not to repeat a pairing
    nCr = (names_len * (names_len - 1)) // size
    previous_pairings = [set(pair) for p in store['history'][-nCr:]
                         for pair in p['attendees']] if 'history' in store else []

    # == Handle Random Pairs ==
    attempts = 1
    max_attempts = 25
    while number_of_pairings:
        # Only add an extra person per group unless at the last pair,
        # then clear out all remaining people into the last group.
        if out_remainder > 0 and number_of_pairings:
            if number_of_pairings > 1:
                remainder = 1
                out_remainder -= 1
            else:
                remainder = out_remainder
                out_remainder = 0
        else:
            remainder = 0

        local_size = size + remainder
        local_names = names[:]
        pairing = []

        while local_size:
            name = random.choice(local_names)
            local_names.remove(name)
            pairing.append(name)
            local_size -= 1

        if not any_pair:
            pairing = frozenset(pairing)
            if pairing in previous_pairings and attempts <= max_attempts:
                print('Generated already existing pair, going to try again ({} attempt(s) so far)'.
                      format(attempts))
                attempts += 1
                continue
            elif attempts > max_attempts:
                print('Max randomizing attempts reached, Got to start over again!!!!')
                return False

        # Store difference of names (remaining people to pair)
        names = [n for n in names if n in local_names]
        todays_meeting['attendees'].append(pairing)
        number_of_pairings -= 1

    # == Print Pairs ==
    print('\n== Pairings for {:%m/%d/%Y} ==\n'.format(todays_meeting['date']))
    pretty_attendees = '\n'.join(
        format_attendees(pair, max_pair_size) for pair in todays_meeting['attendees'])
    print(pretty_attendees)
    pretty_whos_out = format_attendees([o[0] + '.' + o[1:] for o in whos_out], at=False)
    print("(Who's out: {})".format(pretty_whos_out))
    if names:
        # names should be empty if everyone is paired.
        sys.exit("\n ERROR: These people were not paired: {}".format(', '.join(names)))

    # == Generate meeting and Save ==
    while True:
        if force_create:
            answer = 'yes'
        else:
            answer = input('\nAccept and write to shelf storage? (y/n) ').lower()

        if answer in YES:
            if found_upcoming:
                del store['upcoming']

            store['history'].append(todays_meeting)
            send_to_slack(pretty_attendees, pretty_whos_out, sc)
            break
        elif answer in NO:
            print("NOT saving these pairings.")
            break
        else:
            print("Please respond with 'yes' or 'no'")

    return True


def format_attendees(l, t=5, at=True):
    """Auxiliary function to format a list of names into proper English. It also appends
    a random google hangout URL at the end of '@' mentioned attendees.

    Args:
        l (list): A list of strings (names)
        t (int): Threshold, after reaching this point, stop listing names
        at (Optional[bool]): Defaults to True, prepends '@' to usernames so they are linked in Slack.

    Note:
        Adapted from a StackOverflow post, but can't find it now.

    Returns:
        str: A list of names - such as @john, @susan, and @bill
    """
    length = len(l)
    l = [('@' if at else '') + k for k in l]
    if length <= 2:
        att = " & ".join(l)
    elif length < t:
        att = ", ".join(l[:-1]) + " & " + l[-1]
    elif length == t:
        att = ", ".join(l[:-1]) + " & 1 other"
    else:
        att = ", ".join(l[:t - 1]) + " & {} others".format(length - (t - 1))

    return att + " - " + get_google_hangout_url() if at else att


def send_to_slack(pretty_attendees, pretty_whos_out, sc):
    """Send today's meeting lineup to the specified SLACK_CHANNEL

    Args:
        pretty_attendees (list): A list of strings (generated name pairs)
        pretty_whos_out (list): A list of strings (people not in today's meetings)
        sc (SlackClient): An instance of SlackClient
    """
    sc.api_call(
        "chat.postMessage",
        channel=SLACK_CHANNEL,
        as_user=True,
        text="Today's :coffee: and :bagel: pairs are below!")
    sc.api_call(
        "chat.postMessage",
        channel=SLACK_CHANNEL,
        as_user=True,
        text=pretty_attendees,
        link_names=True)
    if pretty_whos_out:
        sc.api_call(
            "chat.postMessage",
            channel=SLACK_CHANNEL,
            as_user=True,
            text="(Who's out: {})".format(pretty_whos_out))
    print('Slack message posted to {}!'.format(SLACK_CHANNEL))


def main(args):
    """
    Initialize the shelf, possibly sync to s3, then generate a meeting, close
    the shelf and maybe sync the shelf again.

    Args:
        args (ArgumentParser args): Parsed arguments that impact how the generate_meeting runs
    """
    if args.s3_sync:
        download_shelve_from_s3()

    store, sc = initialize(update_everyone=True)
    try:
        max_attempts, attempt = 100, 1
        success = False
        while not success:
            success = create_meetings(
                store,
                sc,
                size=args.size,
                whos_out=args.whos_out,
                pairs=args.pairs,
                force_create=args.force_create,
                any_pair=attempt > max_attempts)
            attempt += 1
    finally:
        store.close()
        if args.s3_sync:
            upload_shelve_to_s3()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
        description='Generate random Coffee & Bagel meetups to promote synergy!')
    parser.add_argument(
        '--out',
        '-o',
        dest='whos_out',
        metavar='P',
        nargs='+',
        required=False,
        default=[],
        help="list of people to exclude in today's meetings (usernames only)")
    parser.add_argument(
        '--pair',
        '-p',
        dest='pairs',
        metavar='P+J',
        nargs='+',
        required=False,
        default=[],
        help="list of username pairs (each pair is separated by space, format is username+username)"
        " to set explicitly in today's meetings (ex. --pair bill+susy). Any names outside this list will be"
        " paired randomly like usual.")
    parser.add_argument(
        '--size',
        '-s',
        dest='size',
        type=int,
        required=False,
        default=PAIRING_SIZE,
        help="size of pairings (default set in config.py)")
    parser.add_argument(
        '--force-create',
        action='store_true',
        help='Create random meetings without user confirmation.')
    parser.add_argument(
        '--from-cron', action='store_true', help='Silence all print statements (stdout).')
    parser.add_argument(
        '--s3-sync',
        action='store_true',
        help='Synchronize SHELVE_FILE with AWS S3 before and after checking attendance.')
    parsed_args = parser.parse_args()

    if parsed_args.from_cron:
        with nostdout():
            main(parsed_args)
    else:
        main(parsed_args)
