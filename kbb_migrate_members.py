#!/usr/bin/env python3
"""Invite members of an old KBB room to its new announcement room."""

import argparse
import http.client
import os
import re
import sys
from pathlib import Path

from kbb_invite import dooray_request, numeric_id


BATCH_SIZE = 20


def get_rooms(token):
    channels = dooray_request(token, "/messenger/v1/channels").get("result")
    if not isinstance(channels, list):
        raise RuntimeError("Dooray returned no channel list")
    return {channel["id"]: channel for channel in channels}


def member_ids(room):
    participants = (room.get("users") or {}).get("participants")
    if not isinstance(participants, list):
        raise RuntimeError(f"Dooray returned no participant list for room {room['id']}")
    members = set()
    for participant in participants:
        member = participant.get("member")
        if participant.get("type") != "member" and member is None:
            continue
        member = member or {}
        member_id = member.get("organizationMemberId") or member.get("organizationmemberid")
        if not numeric_id(member_id):
            raise RuntimeError(f"Dooray returned an invalid member ID for room {room['id']}")
        members.add(member_id)
    return members


def migrate(token, source_id, destination_id, apply):
    rooms = get_rooms(token)
    source = rooms.get(source_id)
    destination = rooms.get(destination_id)
    if source is None or destination is None:
        raise RuntimeError("Both rooms must appear in the token owner's channel list")
    role = (destination.get("me") or {}).get("role") or destination.get("role")
    if role not in ("creator", "admin"):
        raise RuntimeError("The token owner must be an admin of the destination room")

    source_members = member_ids(source)
    destination_members = member_ids(destination)
    missing = sorted(source_members - destination_members)
    print(f"Source room {source_id} ({source.get('title') or 'untitled'})")
    print(f"Destination room {destination_id} ({destination.get('title') or 'untitled'})")
    print(f"Source members: {len(source_members)}, already in destination: "
          f"{len(source_members) - len(missing)}, to invite: {len(missing)}", flush=True)

    capacity = destination.get("capacity")
    if isinstance(capacity, int) and capacity > 0 and missing:
        if len(destination_members) + len(missing) > capacity:
            raise RuntimeError(f"The migration would exceed the destination capacity of {capacity}")
    if not apply:
        print("Preview complete. Pass --apply to send the invitations.")
        return
    if not missing:
        print("All source members are already in the destination room.")
        return

    join_path = f"/messenger/v1/channels/{destination_id}/members/join"
    for offset in range(0, len(missing), BATCH_SIZE):
        batch = missing[offset:offset + BATCH_SIZE]
        try:
            dooray_request(token, join_path, method="POST", data={"memberIds": batch})
        except (RuntimeError, OSError, http.client.HTTPException) as exc:
            raise RuntimeError(
                f"Batch {offset // BATCH_SIZE + 1} failed after {offset} invitations were accepted. "
                f"Rerun the preview to check the remaining roster. {exc}"
            ) from exc

    updated_room = get_rooms(token).get(destination_id)
    if updated_room is None:
        raise RuntimeError("Dooray did not return the destination room for verification")
    remaining = source_members - member_ids(updated_room)
    if remaining:
        raise RuntimeError(f"Could not confirm {len(remaining)} source members in the destination room")
    print(f"Verified all {len(source_members)} source members in the destination room.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-room-id", required=True, help="Old KBB room ID")
    parser.add_argument("--destination-room-id", required=True, help="New announcement room ID")
    parser.add_argument("--token-file", type=Path, help="Read the token here instead of DOORAY_TOKEN")
    parser.add_argument("--apply", action="store_true", help="Send the invitations after reading both rosters")
    args = parser.parse_args()
    if not all(map(numeric_id, (args.source_room_id, args.destination_room_id))):
        parser.error("room IDs must be numeric Dooray IDs")
    if args.source_room_id == args.destination_room_id:
        parser.error("the source and destination must be different rooms")

    try:
        token = (args.token_file.read_text() if args.token_file else
                 os.environ.get("DOORAY_TOKEN", "")).strip()
        if not re.fullmatch(r"[!-~]+:[!-~]+", token):
            parser.error("set DOORAY_TOKEN or --token-file to a Dooray token in id:secret format")
        migrate(token, args.source_room_id, args.destination_room_id, args.apply)
    except (RuntimeError, OSError, http.client.HTTPException) as exc:
        print(f"kbb_migrate_members: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
