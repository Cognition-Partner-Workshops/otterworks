#!/usr/bin/env python
"""Generate the synthetic mmp_rt fixture in mmp_rt_billing_n.

Deterministic (seed 1). Writes ONLY to MONGODB_MMP_RT_TARGET_N_URI.
Mirrors the source field names/BSON types from .migration/census/source_census.json.
"""
import os
import random
from datetime import datetime, timezone, timedelta

from bson import Decimal128, ObjectId
from pymongo import MongoClient

random.seed(1)

DB = "mmp_rt_billing_n"
BASE = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def dt(days, ms=0):
    return BASE + timedelta(days=days, milliseconds=ms)


def main():
    uri = os.environ["MONGODB_MMP_RT_TARGET_N_URI"]
    db = MongoClient(uri, maxPoolSize=2)[DB]

    cols = ["fx_src_users", "fx_src_folders", "fx_src_documents",
            "fx_src_comments", "fx_src_shares", "fx_src_audit_events"]
    for c in cols:
        db[c].drop()

    # users (50), 2 case-variant dup email groups (4 docs)
    users = []
    uids = []
    for i in range(50):
        uid = ObjectId()
        uids.append(uid)
        email = f"user{i}@example.test"
        if i in (7, 23):
            email = f"User{i}@Example.test"  # dup of a lower-cased twin added below
        users.append({
            "_id": uid,
            "email": email,
            "displayName": f"User {i}",
            "role": random.choice(["admin", "editor", "viewer"]),
            "settings": {"theme": random.choice(["light", "dark"]),
                         "notifications": bool(random.getrandbits(1))},
            "createdAt": dt(i),
        })
    # make the twins: indices 7 and 23 already uppercase variants; add their lower twins
    for i, twin_of in ((46, 7), (47, 23)):
        users[i]["email"] = f"user{twin_of}@example.test"
    db["fx_src_users"].insert_many(users)
    db["fx_src_users"].create_index([("email", 1)], name="email_1")

    # folders (30), ~40% parentId None
    folders = []
    fids = [ObjectId() for _ in range(30)]
    for i in range(30):
        parent = None
        if i > 0 and random.random() >= 0.4:
            parent = fids[random.randrange(i)]
        name = f"folder-{i}"
        folders.append({
            "_id": fids[i],
            "name": name,
            "path": f"/{name}" if parent is None else f"/p/{name}",
            "parentId": parent,
            "ownerId": random.choice(uids),
            "createdAt": dt(i),
        })
    db["fx_src_folders"].insert_many(folders)

    # documents (500), exactly 5 folderId None
    documents = []
    dids = [ObjectId() for _ in range(500)]
    for i in range(500):
        documents.append({
            "_id": dids[i],
            "title": f"Document {i}",
            "ownerId": random.choice(uids),
            "folderId": None if i < 5 else random.choice(fids),
            "tags": random.sample(["alpha", "beta", "gamma", "delta"], k=random.randint(0, 3)),
            "version": random.randint(1, 9),
            "status": random.choice(["draft", "published", "archived"]),
            "sizeBytes": random.randint(100, 100000),
            "price": Decimal128(f"{random.uniform(0, 999):.2f}"),
            "createdAt": dt(i % 100),
            "updatedAt": dt(i % 100, ms=random.randrange(0, 60000, 1000)),
        })
    db["fx_src_documents"].insert_many(documents)
    db["fx_src_documents"].create_index([("ownerId", 1), ("updatedAt", -1)],
                                      name="ownerId_1_updatedAt_-1")

    # comments (1200), exactly 2 orphan documentIds
    comments = []
    for i in range(1200):
        comments.append({
            "_id": ObjectId(),
            "documentId": ObjectId() if i < 2 else random.choice(dids),
            "authorId": random.choice(uids),
            "body": f"comment body {i}",
            "createdAt": dt(i % 200),
            "editedAt": None if random.random() < 0.6 else dt(i % 200, ms=3600000),
        })
    db["fx_src_comments"].insert_many(comments)
    db["fx_src_comments"].create_index([("documentId", 1)], name="documentId_1")

    # shares (300), ~60% expiresAt None
    shares = []
    for i in range(300):
        shares.append({
            "_id": ObjectId(),
            "documentId": random.choice(dids),
            "granteeId": random.choice(uids),
            "permission": random.choice(["view", "comment", "edit"]),
            "expiresAt": None if random.random() < 0.6 else dt(365, ms=i * 1000),
        })
    db["fx_src_shares"].insert_many(shares)

    # audit_events (2000), exactly 10 with string ts
    events = []
    for i in range(2000):
        events.append({
            "_id": ObjectId(),
            "actorId": random.choice(uids),
            "action": random.choice(["create", "update", "delete", "share", "view"]),
            "targetType": random.choice(["document", "folder", "user", "share"]),
            "targetId": ObjectId(),
            "meta": {"ip": f"10.0.0.{i % 255}", "ok": True},
            "ts": "2026-03-04T10:11:12+00:00" if i < 10 else dt(i % 300),
        })
    db["fx_src_audit_events"].insert_many(events)
    db["fx_src_audit_events"].create_index([("ts", 1)], name="ts_1")

    for c in cols:
        print(c, db[c].count_documents({}))


if __name__ == "__main__":
    main()
