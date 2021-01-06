"""
Bagelbot utility functions used by the different scripts.
"""
import logging
import contextlib
import os
import sys
import shelve

import boto3
from botocore.exceptions import ClientError
from slackclient import SlackClient

from config import EMAIL_DOMAIN, S3_BUCKET, S3_PREFIX, SLACK_TOKEN, SHELVE_FILE, SLACK_CHANNEL_ID

logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")

YES = frozenset(["yes", "y", "ye", ""])
NO = frozenset(["no", "n"])


def get_slack_client():
    """Initializes SlackClient for bagelbot's use.

    Note:
        It pulls the required Slack API token from config.py

    Returns:
        sc: A SlackClient instance
    """
    if not SLACK_TOKEN or SLACK_TOKEN == "yourtoken":
        sys.exit("Exiting... SLACK_TOKEN was empty or not updated from the default in config.py.")

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
        store: A shelve instance
    """
    return shelve.open(SHELVE_FILE, writeback=True)


def download_shelve_from_s3():
    """Download the SHELVE_FILE from S3_BUCKET & S3_PREFIX.
    """
    s3 = boto3.resource("s3")
    key = os.path.join(S3_PREFIX, SHELVE_FILE) if S3_PREFIX else SHELVE_FILE
    s3.meta.client.download_file(S3_BUCKET, key, SHELVE_FILE)


def upload_shelve_to_s3():
    """Upload the SHELVE_FILE to S3_BUCKET & S3_PREFIX.
    """
    s3 = boto3.resource("s3")
    key = os.path.join(S3_PREFIX, SHELVE_FILE) if S3_PREFIX else SHELVE_FILE
    s3.meta.client.upload_file(SHELVE_FILE, S3_BUCKET, key)
    logging.info("Storage uploaded to S3 successfully")


class DummyFile:
    """Used to silence stdout when scripts are ran from a cron.

    Note:
        http://stackoverflow.com/q/2828953/76267
    """

    def read(self):
        """
        DummyFile has no read method.
        """
        raise NotImplementedError("No read method for DummyFile")

    def write(self, x):
        """
        Provide a defunct write method to silence stdout.

        Args:
            self (object): DummyFile Instance
            x (str): Text passed to write to DummyFile
        """
        pass


@contextlib.contextmanager
def nostdout():
    """A context used to silence stdout from any bot functions.

    Used when a script is ran as `--from-cron`, that way no stdout is produced.

    Note:
        http://stackoverflow.com/q/2828953/76267
    """
    save_stdout = sys.stdout
    sys.stdout = DummyFile()
    yield
    sys.stdout = save_stdout


def update_everyone_from_slack(store, sc):
    """Updates our store's list of `everyone`.

    This list is comprised of all slack users with
    the specified EMAIL_DOMAIN in config.py that are not deleted or single-channel guests.

    Args:
        store (instance): A persistent, dictionary-like object used to keep
        information about past/future meetings.
        sc (SlackClient): An instance of SlackClient
    """
    if not sc:
        sc = get_slack_client()

    users = sc.api_call( "conversations.members",channel=SLACK_CHANNEL_ID)
    fullusers = [
        sc.api_call( "users.info",user=member)
        for member in users["members"]
    ]
    store["everyone"] = [
        m["user"]["name"]
        for m in fullusers
        if not m["user"]["deleted"]
        and not m["user"]["is_restricted"]
        and not m["user"]["is_bot"]
        and m["user"]["profile"].get("email")
        and m["user"]["profile"]["email"].endswith("@" + EMAIL_DOMAIN)
    ]
