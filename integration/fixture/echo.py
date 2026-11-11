"""Transactional echo for the broker fault smoke test, independent of target routes."""

import os
import time
import uuid

import stomp


class Echo(stomp.ConnectionListener):
    def __init__(self, connection):
        self.connection = connection

    def on_message(self, frame):
        connection = self.connection
        transaction = str(uuid.uuid4())
        connection.begin(transaction=transaction)
        connection.send(destination="REPLAY.SMOKE.OUT", body=frame.body,
                        headers={"requestId": frame.headers["requestId"], "persistent": "true",
                                 "transaction": transaction})
        connection.ack(frame.headers["ack"], transaction=transaction)
        connection.commit(transaction=transaction)


def run():
    while True:
        connection = stomp.Connection12([("broker", 61613)], heartbeats=(1000, 1000), reconnect_attempts_max=1)
        connection.set_listener("echo", Echo(connection))
        try:
            connection.connect(os.environ["REPLAY_BROKER_USER"], os.environ["REPLAY_BROKER_PASSWORD"], wait=True)
            connection.subscribe("REPLAY.SMOKE.IN", "echo", ack="client-individual",
                                 headers={"subscription-type": "ANYCAST"})
            print("Transactional echo subscribed", flush=True)
            while connection.is_connected():
                time.sleep(0.1)
        except (OSError, stomp.exception.StompException):
            time.sleep(0.25)
        finally:
            if connection.is_connected():
                connection.disconnect()


if __name__ == "__main__":
    run()
