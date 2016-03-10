from __future__ import print_function

import sys
import shelve

from slackclient import SlackClient

from config import EMAIL_DOMAIN, SLACK_TOKEN, SHELVE_FILE

YES = frozenset(['yes','y', 'ye', ''])
NO = frozenset(['no','n'])


def get_slack_client():
    """Initializes SlackClient for bagelbot's use.

    Note:
        It pulls the required Slack API token from config.py

    Returns:
        SlackClient instance
    """
    if not SLACK_TOKEN or SLACK_TOKEN == 'yourtoken':
        sys.exit('Exiting... SLACK_TOKEN was empty or not updated from the default in config.py.')

    return SlackClient(SLACK_TOKEN)


def initialize(update_everyone=False):
    """Used to initalize resources - both the 'shelf' store and slack client - and return them.

    Args:
        update_everyone (Optional[bool]): If True, updates all users in the EMAIL_DOMAIN
            from slack. Defaults to False.

    Returns:
        store: A shelve instance
        sc: A SlackClient instance
    """
    store = open_store()
    sc = get_slack_client()
    if update_everyone:
        update_everyone_from_slack(store, sc)
    return store, sc


def open_store():
    """Open the SHELVE_FILE and return an open shelf instance.

    Returns:
        instance
    """
    return shelve.open(SHELVE_FILE, writeback=True)


def update_everyone_from_slack(store, sc):
    """Updates our store's list of `everyone`.

    This list is comprised of all slack users with
    the specified EMAIL_DOMAIN in config.py.

    Args:
        store (instance): A persistent, dictionary-like object used to keep information about past/future meetings
        sc (SlackClient): An instance of SlackClient
    """
    if not sc:
        sc = get_slack_client()

    users = sc.api_call("users.list")
    store['everyone'] = [m['name'] for m in users['members']
                         if not m['deleted'] and m['profile'].get('email')
                         and m['profile']['email'].endswith('@' + EMAIL_DOMAIN)]
