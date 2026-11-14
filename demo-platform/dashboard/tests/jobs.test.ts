import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type * as k8s from "@kubernetes/client-node";
import { buildRunnerJob, isJobFinished } from "@/lib/jobs";

function runnerEnv(job: k8s.V1Job, name: string): string | undefined {
  return job.spec?.template.spec?.containers[0]?.env?.find((e) => e.name === name)?.value;
}

describe("buildRunnerJob", () => {
  const saved = { ...process.env };
  beforeEach(() => {
    process.env.RUNNER_IMAGE = "example.invalid/runner:test";
    delete process.env.RUNNER_JOB_DEADLINE_SECONDS;
  });
  afterEach(() => {
    process.env = { ...saved };
  });

  it("caps every runner Job with activeDeadlineSeconds", () => {
    const job = buildRunnerJob({ action: "deploy", tenantId: "t1" }, 1);
    expect(job.spec?.activeDeadlineSeconds).toBe(5400);
    expect(job.spec?.backoffLimit).toBe(1);
  });

  it("bounds the runner's deploy step below the Job deadline", () => {
    process.env.RUNNER_JOB_DEADLINE_SECONDS = "1800";
    const job = buildRunnerJob({ action: "deploy", tenantId: "t1" }, 1);
    expect(job.spec?.activeDeadlineSeconds).toBe(1800);
    expect(runnerEnv(job, "RUNNER_OP_TIMEOUT_SECONDS")).toBe("1500");
  });

  it("ignores an invalid deadline override", () => {
    process.env.RUNNER_JOB_DEADLINE_SECONDS = "soon";
    const job = buildRunnerJob({ action: "teardown", tenantId: "t1" }, 1);
    expect(job.spec?.activeDeadlineSeconds).toBe(5400);
  });

  it("keeps secrets as secretKeyRef references", () => {
    const job = buildRunnerJob({ action: "deploy", tenantId: "t1" }, 1);
    const dbPassword = job.spec?.template.spec?.containers[0]?.env?.find((e) => e.name === "DB_PASSWORD");
    expect(dbPassword?.value).toBeUndefined();
    expect(dbPassword?.valueFrom?.secretKeyRef?.key).toBe("DB_PASSWORD");
  });
});

describe("isJobFinished", () => {
  const job = (status: k8s.V1JobStatus | undefined): k8s.V1Job => ({ status });

  it("treats a just-created Job as running", () => {
    expect(isJobFinished(job(undefined))).toBe(false);
    expect(isJobFinished(job({}))).toBe(false);
  });

  it("treats a Job with an active pod as running even after a failed attempt", () => {
    expect(isJobFinished(job({ active: 1, failed: 1 }))).toBe(false);
  });

  it("treats a DeadlineExceeded Job as finished before pod counts are reported", () => {
    expect(
      isJobFinished(
        job({ active: 0, conditions: [{ type: "Failed", status: "True", reason: "DeadlineExceeded" }] }),
      ),
    ).toBe(true);
  });

  it("treats Complete and counted terminal Jobs as finished", () => {
    expect(isJobFinished(job({ conditions: [{ type: "Complete", status: "True" }] }))).toBe(true);
    expect(isJobFinished(job({ succeeded: 1 }))).toBe(true);
    expect(isJobFinished(job({ failed: 2 }))).toBe(true);
  });

  it("ignores non-true terminal conditions", () => {
    expect(isJobFinished(job({ active: 1, conditions: [{ type: "Failed", status: "False" }] }))).toBe(false);
  });
});
