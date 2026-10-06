import net from "node:net";
import type { AddressInfo } from "node:net";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { DynamoDBClient, GetItemCommand } from "@aws-sdk/client-dynamodb";
import {
  DDB_CONNECTION_TIMEOUT_MS,
  DDB_MAX_ATTEMPTS,
  DDB_REQUEST_TIMEOUT_MS,
  controlClientConfig,
} from "@/lib/control";

// A TCP endpoint that accepts connections and never answers: the shape of a
// stalled DynamoDB connection.
let server: net.Server;
let endpoint: string;
let connections = 0;
const sockets = new Set<net.Socket>();

beforeAll(async () => {
  server = net.createServer((s) => {
    connections += 1;
    sockets.add(s);
    s.on("close", () => sockets.delete(s));
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  endpoint = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});

afterAll(async () => {
  for (const s of sockets) s.destroy();
  await new Promise<void>((resolve) => server.close(() => resolve()));
});

const credentials = { accessKeyId: "test", secretAccessKey: "test" };
const get = new GetItemCommand({ TableName: "t", Key: { PK: { S: "x" }, SK: { S: "y" } } });

describe("control-table DynamoDB client", () => {
  it("configures explicit timeouts and a bounded retry budget", () => {
    const cfg = controlClientConfig();
    expect(cfg.maxAttempts).toBe(DDB_MAX_ATTEMPTS);
    expect(cfg.retryMode).toBe("standard");
    expect(cfg.requestHandler).toEqual({
      connectionTimeout: DDB_CONNECTION_TIMEOUT_MS,
      requestTimeout: DDB_REQUEST_TIMEOUT_MS,
    });
  });

  it("an SDK client without explicit timeouts never settles on a stalled connection", async () => {
    const client = new DynamoDBClient({ region: "us-east-1", endpoint, credentials, maxAttempts: 1 });
    const outcome = await Promise.race([
      client.send(get).then(
        () => "settled",
        () => "settled",
      ),
      new Promise((resolve) => setTimeout(() => resolve("still-waiting"), DDB_REQUEST_TIMEOUT_MS + 2000)),
    ]);
    client.destroy();
    expect(outcome).toBe("still-waiting");
  }, 15_000);

  it("fails a stalled request within the bounded attempt budget", async () => {
    connections = 0;
    const client = new DynamoDBClient({ ...controlClientConfig(), endpoint, credentials });
    const started = Date.now();
    const err = await client.send(get).then(
      () => null,
      (e: unknown) => e,
    );
    const elapsed = Date.now() - started;
    client.destroy();
    expect(err).toBeInstanceOf(Error);
    expect(connections).toBe(DDB_MAX_ATTEMPTS);
    // 3 attempts x 5s request timeout plus jittered backoff (max 20s per retry
    // in standard mode, but small for the first two).
    expect(elapsed).toBeLessThan(DDB_MAX_ATTEMPTS * DDB_REQUEST_TIMEOUT_MS + 10_000);
  }, 40_000);
});
