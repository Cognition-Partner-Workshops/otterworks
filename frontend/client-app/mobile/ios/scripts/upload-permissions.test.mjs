import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import test from "node:test";

test("iOS file uploads declare camera, photo library and microphone usage", () => {
  const plist = fileURLToPath(new URL("../App/App/Info.plist", import.meta.url));
  const info = JSON.parse(execFileSync("plutil", ["-convert", "json", "-o", "-", plist], { encoding: "utf8" }));
  for (const key of ["NSCameraUsageDescription", "NSPhotoLibraryUsageDescription", "NSMicrophoneUsageDescription"]) {
    assert.equal(typeof info[key], "string", key);
    assert.ok(info[key].trim().length > 0, key);
    assert.match(info[key], /upload.*OtterWorks/i, key);
  }
});
