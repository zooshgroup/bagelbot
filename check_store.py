#!/usr/bin/env python
"""
Simple script for checking what all is in `meetings.shelve` - our
persistent object for storing meeting history.
"""
from __future__ import print_function

from pprint import pprint

from utils import open_store

store = open_store()
for key in store:
    print(' == {} == '.format(key))
    pprint(store[key])
    print()
store.close()
