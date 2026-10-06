// Runs the real checkout() against DynamoDB Local. Opt-in: set
// DDB_LOCAL_ENDPOINT (e.g. http://127.0.0.1:8000 from
// `docker run -p 8000:8000 amazon/dynamodb-local`); skipped otherwise.
import { beforeAll, beforeEach, describe, expect, it } from "vitest";
import {
  CreateTableCommand,
  DeleteTableCommand,
  DynamoDBClient,
  GetItemCommand,
  PutItemCommand,
} from "@aws-sdk/client-dynamodb";

const endpoint = process.env.DDB_LOCAL_ENDPOINT;
const TABLE = "otterworks-demo-control-test";

describe.skipIf(!endpoint)("checkout against DynamoDB Local", () => {
  let raw: DynamoDBClient;
  let control: typeof import("@/lib/control");
  const now = () => Math.floor(Date.now() / 1000);
  const base = {
    owner: "alice",
    branch: "workshop-x",
    tier: "A" as const,
    ttlSeconds: 3600,
    hostSuffix: "demo.example",
  };

  beforeAll(async () => {
    process.env.CONTROL_TABLE = TABLE;
    process.env.AWS_ENDPOINT_URL_DYNAMODB = endpoint;
    process.env.AWS_ACCESS_KEY_ID = "local";
    process.env.AWS_SECRET_ACCESS_KEY = "local";
    raw = new DynamoDBClient({ region: "us-east-1", endpoint });
    control = await import("@/lib/control");
  });

  beforeEach(async () => {
    await raw.send(new DeleteTableCommand({ TableName: TABLE })).catch(() => {});
    await raw.send(
      new CreateTableCommand({
        TableName: TABLE,
        BillingMode: "PAY_PER_REQUEST",
        AttributeDefinitions: [
          { AttributeName: "PK", AttributeType: "S" },
          { AttributeName: "SK", AttributeType: "S" },
        ],
        KeySchema: [
          { AttributeName: "PK", KeyType: "HASH" },
          { AttributeName: "SK", KeyType: "RANGE" },
        ],
      }),
    );
  });

  const lockOf = async (id: string) =>
    (await raw.send(new GetItemCommand({ TableName: TABLE, Key: { PK: { S: `LOCK#${id}` }, SK: { S: "LOCK" } } })))
      .Item;
  const putLock = (id: string, lockTtl: number) =>
    raw.send(
      new PutItemCommand({
        TableName: TABLE,
        Item: {
          PK: { S: `LOCK#${id}` },
          SK: { S: "LOCK" },
          owner: { S: "bob" },
          acquired_at: { N: String(lockTtl - 900) },
          lock_ttl: { N: String(lockTtl) },
          ttl: { N: String(lockTtl) },
        },
      }),
    );

  it("checks out an id whose lock has lapsed but not yet been TTL-deleted", async () => {
    await putLock("lapsed", now() - 60);
    const t = await control.checkout({ id: "lapsed", ...base });
    expect(t.status).toBe("deploying");
    expect((await lockOf("lapsed"))?.owner?.S).toBe("alice");
  });

  it("still refuses an id whose lock is live", async () => {
    await putLock("held", now() + 600);
    await expect(control.checkout({ id: "held", ...base })).rejects.toThrow(control.LockConflictError);
    expect((await lockOf("held"))?.owner?.S).toBe("bob");
  });

  it("refuses a live tenant even after its lock lapsed, and leaves no lock of its own behind", async () => {
    await control.checkout({ id: "live", ...base });
    await putLock("live", now() - 60);
    await expect(control.checkout({ id: "live", ...base, owner: "carol" })).rejects.toThrow(
      control.LockConflictError,
    );
    expect(await lockOf("live")).toBeUndefined();
  });

  it("releases its lock when the tenant write fails outright", async () => {
    // A >400KB item makes the META PutItem fail with a ValidationException
    // after the lock PutItem has succeeded.
    await expect(
      control.checkout({ id: "toolarge", ...base, branch: "b".repeat(410 * 1024) }),
    ).rejects.toThrow();
    expect(await lockOf("toolarge")).toBeUndefined();
    await expect(control.checkout({ id: "toolarge", ...base })).resolves.toMatchObject({ status: "deploying" });
  });
});
