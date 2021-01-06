#!/usr/bin/env python
"""
Simple script for generating some simple meeting attendance statistics
using history of past meetings.
"""
from utils import open_store

store = open_store()
everyone = store["everyone"]
history = store["history"]
store.close()

attendance = {p: {"total": 0, "dates": []} for p in everyone}
for meeting in history:
    for pair in meeting["attendees"]:
        for person in pair:
            if person in attendance:
                attendance[person]["total"] += 1
                attendance[person]["dates"].append(meeting["date"])

for person, info in attendance.iteritems():
    print("=== {} ===".format(person))
    print(" Total Attended: {}".format(info["total"]))
    print(
        " Meeting Dates: {}".format(
            ", ".join(d.strftime("%Y-%m-%d") for d in sorted(info["dates"]))
        )
    )
    print()
