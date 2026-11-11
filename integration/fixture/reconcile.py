"""Bring a broker volume created from an older broker.xml in line with the current fixture.

Artemis keeps queues and address routing types in its journal. A durable subscription queue
auto-created as ANYCAST on a topic address stays ANYCAST after the fixture changes, and it
also added ANYCAST to the address, so a STOMP durable resubscribe still fails (AMQ339016).
Convert those queues in place, keeping their messages, then drop ANYCAST from the address.
"""

import json
import os
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

CORE = {"a": "urn:activemq:core"}
BROKER_XML = Path("integration/fixture/broker.xml")
BROKER_IMAGE = "apache/activemq-artemis:2.40.0-alpine"


def multicast_addresses(path=BROKER_XML):
    core = ET.parse(path).getroot().find("a:core", CORE)
    return {a.get("name") for a in core.findall("a:addresses/a:address", CORE)
            if a.find("a:multicast", CORE) is not None and a.find("a:anycast", CORE) is None}


def artemis(container, *args):
    # Its own container on the broker's network: a docker exec JVM shares the broker's 512m limit and,
    # next to the healthcheck JVM, gets the broker OOM-killed.
    command = ["docker", "run", "--rm", "--network", f"container:{container}",
               "--entrypoint", "/opt/activemq-artemis/bin/artemis", BROKER_IMAGE, *args, "--url", "tcp://localhost:61616",
               "--user", os.environ["REPLAY_BROKER_USER"], "--password", os.environ["REPLAY_BROKER_PASSWORD"]]
    try:
        return subprocess.run(command, check=True, capture_output=True, text=True, timeout=120).stdout
    except subprocess.CalledProcessError as error:
        raise SystemExit(f"artemis {' '.join(args[:2])} failed on {container}: {error.stdout}{error.stderr}") from error


def reconcile(container=None, run=artemis, path=BROKER_XML):
    container = container or os.environ["REPLAY_BROKER_CONTAINER"]
    topics = multicast_addresses(path)
    stat = run(container, "queue", "stat", "--json", "--maxRows", "10000")
    stale = [q for q in json.loads(stat[stat.index("{"):])["data"]
             if q["address"] in topics and q["routingType"] != "MULTICAST"]
    for queue in stale:
        run(container, "queue", "update", "--name", queue["name"], "--address", queue["address"],
            "--multicast", "--silent")
        print(f"Converted {queue['name']} on topic {queue['address']} from {queue['routingType']} "
              f"to MULTICAST ({queue['messageCount']} messages kept)")
    anycast = sorted(a for a in topics if "ANYCAST" in re.search(
        r"routingTypes=\{([^}]*)\}", run(container, "address", "show", "--name", a)).group(1).split(","))
    for address in anycast:
        run(container, "address", "update", "--name", address, "--multicast", "--no-anycast")
        print(f"Removed ANYCAST routing from topic {address}")
    print(f"Broker topics match the fixture ({len(stale)} queues converted, {len(anycast)} addresses updated)")
    return [q["name"] for q in stale], anycast


if __name__ == "__main__":
    reconcile()
