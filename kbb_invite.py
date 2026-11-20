#!/usr/bin/env python3
"""Invite the authors of KBB subscription tasks to a Dooray announcement room."""

import argparse
import fcntl
import http.client
import itertools
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlencode


PAGE_SIZE = 100


class DoorayError(RuntimeError):
    def __init__(self, method, status, code):
        super().__init__(f"Dooray {method} failed (HTTP {status}, resultCode {code})")
        self.status = status


def dooray_request(token, path, *, method="GET", params=None, data=None):
    headers = {"Authorization": f"dooray-api {token}", "Accept": "application/json"}
    body = None
    if params:
        path += "?" + urlencode(params)
    if data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data)

    connection = http.client.HTTPSConnection("api.gov-dooray.com", timeout=15)
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        status = response.status
        raw = response.read()
    finally:
        connection.close()

    try:
        payload = json.loads(raw)
    except ValueError:
        raise DoorayError(method, status, "unavailable") from None
    header = payload.get("header") if isinstance(payload, dict) else None
    if not isinstance(header, dict):
        raise DoorayError(method, status, "unavailable")
    code = header.get("resultCode")
    if status != 200 or header.get("isSuccessful") is not True:
        raise DoorayError(method, status, code if isinstance(code, int) else "unavailable")
    return payload


def numeric_id(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9]+", value) is not None


def find_applications(token, project_id, state_dir):
    """Find open tasks that need invitations or still need to be marked Done."""
    pending = {}
    awaiting_completion = []
    seen = set()
    for page in itertools.count():
        payload = dooray_request(token, f"/project/v1/projects/{project_id}/posts", params={
            "order": "createdAt",
            "page": page,
            "size": PAGE_SIZE,
        })
        posts = payload.get("result")
        if not isinstance(posts, list):
            raise RuntimeError("Dooray returned no task list")
        if not posts:
            break

        previous_count = len(seen)
        for post in posts:
            post_id = post.get("id")
            if not numeric_id(post_id):
                raise RuntimeError("Dooray returned an invalid task ID")
            if post_id in seen:
                continue
            seen.add(post_id)
            if post.get("closed") or post.get("workflowClass") == "closed":
                continue
            if (state_dir / post_id).exists():
                awaiting_completion.append(post_id)
                continue

            author = (post.get("users") or {}).get("from") or {}
            if author.get("type") != "member":
                continue
            member = author.get("member") or {}
            member_id = member.get("organizationMemberId") or member.get("organizationmemberid")
            if not numeric_id(member_id):
                raise RuntimeError(f"Task {post_id} has no valid Dooray author ID")
            pending.setdefault(member_id, []).append(post_id)

        if len(seen) == previous_count:
            raise RuntimeError("Dooray repeated a task page without returning new tasks")
        total = payload.get("totalCount")
        if isinstance(total, int) and len(seen) >= total:
            break
        if not isinstance(total, int) and len(posts) < PAGE_SIZE:
            break
    return pending, awaiting_completion


def room_members(token, channel_id):
    channels = dooray_request(token, "/messenger/v1/channels").get("result")
    if not isinstance(channels, list):
        raise RuntimeError("Dooray returned no channel list")
    for channel in channels:
        if channel.get("id") != channel_id:
            continue
        role = (channel.get("me") or {}).get("role") or channel.get("role")
        if role not in ("creator", "admin"):
            raise RuntimeError("The Dooray token must belong to a room admin")
        participants = (channel.get("users") or {}).get("participants")
        if not isinstance(participants, list):
            raise RuntimeError("Dooray returned no participant list for the configured room")
        members = set()
        for participant in participants:
            member = participant.get("member") or {}
            member_id = member.get("organizationMemberId") or member.get("organizationmemberid")
            if numeric_id(member_id):
                members.add(member_id)
        print(f"Room {channel_id}: {channel.get('title') or '(untitled)'}", flush=True)
        return members
    raise RuntimeError("The configured room is absent from the token owner's channel list")


def mark_applications_done(token, project_id, post_ids):
    completed = 0
    for post_id in post_ids:
        try:
            dooray_request(token, f"/project/v1/projects/{project_id}/posts/{post_id}/set-done",
                           method="POST")
        except DoorayError as exc:
            if exc.status not in (200, 400, 404, 409):
                raise RuntimeError(f"Could not mark task {post_id} Done: {exc}") from exc
            print(f"Could not mark task {post_id} Done: {exc}", file=sys.stderr)
        else:
            completed += 1
    return completed


def process(token, project_id, channel_id, state_dir, apply):
    pending, awaiting_completion = find_applications(token, project_id, state_dir)
    members = room_members(token, channel_id)
    invited = already_in_room = failed = 0
    for member_id, post_ids in pending.items():
        if not apply:
            action = "already in room" if member_id in members else "would invite"
            print(f"Tasks {', '.join(post_ids)}: {action} member {member_id}")
            continue
        if member_id in members:
            already_in_room += 1
        else:
            try:
                dooray_request(token, f"/messenger/v1/channels/{channel_id}/members/join",
                               method="POST", data={"memberIds": [member_id]})
            except DoorayError as exc:
                if exc.status not in (200, 400, 404, 409):
                    raise
                print(f"Tasks {', '.join(post_ids)}: {exc}", file=sys.stderr)
                failed += 1
                continue
            invited += 1

        for post_id in post_ids:
            # Persist the invitation result before attempting the status update.
            (state_dir / post_id).touch()
            awaiting_completion.append(post_id)

    if not apply:
        print(f"Preview: {len(pending)} applicants")
        for post_id in awaiting_completion:
            print(f"Task {post_id}: would mark Done")
        return 0

    print(f"Invited: {invited}, already in room: {already_in_room}, failed: {failed}", flush=True)
    completed = mark_applications_done(token, project_id, awaiting_completion)
    completion_failures = len(awaiting_completion) - completed
    print(f"Tasks marked Done: {completed}, status update failures: {completion_failures}")
    return int(failed > 0 or completion_failures > 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--channel-id", required=True)
    parser.add_argument("--state-dir", required=True, type=Path)
    parser.add_argument("--token-file", type=Path, help="Read the token here instead of DOORAY_TOKEN")
    parser.add_argument("--apply", action="store_true", help="Send invitations and mark applications Done")
    args = parser.parse_args()
    if not all(map(numeric_id, (args.project_id, args.channel_id))):
        parser.error("--project-id and --channel-id must be numeric Dooray IDs")

    state_dir = args.state_dir / f"{args.project_id}-{args.channel_id}"
    try:
        token = (args.token_file.read_text() if args.token_file else
                 os.environ.get("DOORAY_TOKEN", "")).strip()
        if not re.fullmatch(r"[!-~]+:[!-~]+", token):
            parser.error("set DOORAY_TOKEN or --token-file to a Dooray token in id:secret format")
        if not args.apply:
            return process(token, args.project_id, args.channel_id, state_dir, apply=False)

        os.umask(0o077)
        state_dir.mkdir(parents=True, exist_ok=True)
        with (state_dir / ".lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                print("Another invite run is in progress")
                return 0
            return process(token, args.project_id, args.channel_id, state_dir, apply=True)
    except (RuntimeError, OSError, http.client.HTTPException) as exc:
        print(f"kbb_invite: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
