// @vitest-environment node
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import config, { webBuildTarget } from "../../vite.config";

const nativeRoot = new URL("../../mobile/ios/App/", import.meta.url);

describe("iOS web bundle deployment floor", () => {
  it("keeps every Xcode configuration and Swift package on the same floor", () => {
    const project = readFileSync(fileURLToPath(new URL("App.xcodeproj/project.pbxproj", nativeRoot)), "utf8");
    const swiftPackage = readFileSync(fileURLToPath(new URL("CapApp-SPM/Package.swift", nativeRoot)), "utf8");
    const deploymentTargets = [...project.matchAll(/IPHONEOS_DEPLOYMENT_TARGET\s*=\s*(\d+(?:\.\d+)*);/g)]
      .map((match) => Number(match[1]));
    const packageTargets = [...swiftPackage.matchAll(/\.iOS\(\.v(\d+(?:_\d+)*)\)/g)]
      .map((match) => Number(match[1].replace(/_/g, ".")));

    expect(deploymentTargets.length).toBeGreaterThan(0);
    expect(packageTargets).toHaveLength(1);
    expect(new Set(deploymentTargets)).toEqual(new Set(packageTargets));

    const floor = packageTargets[0];
    expect(webBuildTarget).toEqual(["es2021", `safari${floor}`, `ios${floor}`]);
    expect(config.build?.target).toEqual(webBuildTarget);
    expect(config.build?.cssTarget).toEqual(webBuildTarget);
  });
});
