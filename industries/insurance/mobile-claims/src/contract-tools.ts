import { execFileSync } from "node:child_process";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

// Local stand-ins for the hub: xmllint for the receive-port schema check and
// xsltproc for the Fnol_to_CanonicalClaim map.
export const CONTRACT = join(__dirname, "..", "contract");
export const XSD = join(CONTRACT, "ACORD_ClaimsNotificationAddRq.xsd");
export const MAP = join(CONTRACT, "Fnol_to_CanonicalClaim.xslt");
export const CORPUS = join(CONTRACT, "corpus");

export const hasTool = (bin: string) => {
  try {
    execFileSync(bin, ["--version"], { stdio: "pipe" });
    return true;
  } catch {
    return false;
  }
};

export const validate = (path: string) =>
  execFileSync("xmllint", ["--noout", "--schema", XSD, path], { stdio: "pipe" });

export const mapToCanonical = (path: string) =>
  execFileSync("xsltproc", [MAP, path], { stdio: "pipe" }).toString().trim();

export const corpusIds = () =>
  readdirSync(CORPUS)
    .filter((f) => f.endsWith(".fnol.xml"))
    .map((f) => f.replace(".fnol.xml", ""))
    .sort();
