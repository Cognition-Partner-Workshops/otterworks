#!/usr/bin/env node
// Local stand-in for the API gateway so the Capacitor shell can be walked in the
// iOS Simulator without the backend stack. No dependencies; Node 18+.
//
//   node tools/gateway-mock.mjs            # listens on :8080, serves /api/v1/*
//   PORT=9090 FNOL_OUT=/tmp/fnol node tools/gateway-mock.mjs
//
// Every request is logged as one line. POST /api/v1/claims/fnol bodies are written to
// FNOL_OUT (default ./fnol-received), rejected with 422 if the TaxId is unmasked, and
// validated with xmllint against FNOL_XSD (default: the vendored hub schema; set
// FNOL_XSD= to skip).
import { createServer } from "node:http";
import { mkdirSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const PORT = Number(process.env.PORT || 8080);
const FNOL_OUT = process.env.FNOL_OUT || "fnol-received";
const FNOL_XSD =
  process.env.FNOL_XSD ??
  join(dirname(fileURLToPath(import.meta.url)), "..", "contract", "ACORD_ClaimsNotificationAddRq.xsd");

// The Capacitor web views and the Vite dev server only.
const LOCAL_ORIGIN = /^(capacitor|ionic):\/\/localhost$|^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/;

const b64url = (o) => Buffer.from(JSON.stringify(o)).toString("base64url");
const USER = {
  id: "u-adjuster-01",
  email: "adjuster@thistlecombe.example",
  display_name: "Field Adjuster",
  created_at: "2026-01-05T09:00:00Z",
};
const token = () =>
  `${b64url({ alg: "none", typ: "JWT" })}.${b64url({ sub: USER.id, email: USER.email })}.mock`;

const now = "2026-10-19T14:30:00Z";
const file = (id, name, mime, size, folder = null, extra = {}) => ({
  id, name, mime_type: mime, size_bytes: size, s3_key: `mock/${id}`, folder_id: folder,
  owner_id: USER.id, version: 1, is_trashed: false, created_at: "2026-10-12T10:00:00Z",
  updated_at: now, ...extra,
});
const FILES = [
  file("f-1", "POL-AUTO-48100 declarations.pdf", "application/pdf", 248_113),
  file("f-2", "CLM-2026-100400 windscreen.jpg", "image/jpeg", 1_204_551),
  file("f-3", "Adjuster roster Q4.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 58_220),
  file("f-4", "Subrogation letter template.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", 33_870, "d-1"),
];
const TRASH = [file("f-9", "Old reserve worksheet.xlsx", "application/vnd.ms-excel", 18_400, null, { is_trashed: true })];
const FOLDERS = [{ id: "d-1", name: "Templates", parent_id: null, owner_id: USER.id, created_at: "2026-09-01T08:00:00Z", updated_at: now }];
const doc = (id, title, words) => ({
  id, title, content: "", owner_id: USER.id, owner_name: USER.display_name, parent_id: null,
  shared_with: [], collaborators: [], tags: [], word_count: words, created_at: "2026-10-10T08:00:00Z", updated_at: now,
});
const DOCS = [
  doc("doc-1", "CLM-2026-100403 adjuster notes", 412),
  doc("doc-2", "Hail event 2026-10 field checklist", 268),
  doc("doc-3", "Large loss review: POL-HOME-48142", 1_031),
];
let SETTINGS = { notification_email: true, notification_in_app: true, notification_desktop: false, theme: "light", language: "en" };
const NOTIFS = [
  { id: "n-1", type: "share", title: "Claim file shared", message: "Priya shared CLM-2026-100403 adjuster notes", read: false, created_at: now },
  { id: "n-2", type: "system", title: "Catastrophe code opened", message: "CAT-2026-14 is open for Harlow County", read: true, created_at: "2026-10-18T07:00:00Z" },
];
const page = (items, q, key = "files") => ({ [key]: items, total: items.length, page: Number(q.get("page") || 1), page_size: Number(q.get("page_size") || 50) });

function send(res, status, body, type = "application/json") {
  res.writeHead(status, { "Content-Type": type });
  res.end(typeof body === "string" ? body : JSON.stringify(body));
}

function handleFnol(body, res) {
  mkdirSync(FNOL_OUT, { recursive: true });
  const rq = (body.match(/<RqUID>([^<]+)<\/RqUID>/) || [])[1] || `rq-${Date.now()}`;
  const claim = (body.match(/<ClaimNumber>([^<]+)<\/ClaimNumber>/) || [])[1] || "";
  if (/<TaxId>[^<]*\d{5,}[^<]*<\/TaxId>|<TaxId>\d{3}-\d{2}-\d{4}<\/TaxId>/.test(body)) {
    console.log(`  fnol ${rq}: REJECTED unmasked TaxId (not saved)`);
    return send(res, 422, { error: "unmasked_tax_id" });
  }
  const path = join(FNOL_OUT, `${rq}.xml`);
  writeFileSync(path, body);
  if (FNOL_XSD) {
    try {
      execFileSync("xmllint", ["--noout", "--schema", FNOL_XSD, path], { stdio: "pipe" });
      console.log(`  fnol ${rq}: valid against ${FNOL_XSD}`);
    } catch (e) {
      const msg = String(e.stderr || e.message).trim();
      console.log(`  fnol ${rq}: INVALID ${msg}`);
      return send(res, 400, { error: "schema_invalid", detail: msg });
    }
  }
  return send(res, 202, { status: "accepted", rq_uid: rq, claim_number: claim });
}

function route(req, res, body) {
  const url = new URL(req.url, "http://mock");
  const p = url.pathname.replace(/^\/api\/v1/, "");
  const q = url.searchParams;
  const m = req.method;

  if (m === "POST" && (p === "/auth/login" || p === "/auth/register")) {
    if (p === "/auth/register") {
      try { const b = JSON.parse(body || "{}"); if (b.display_name || b.displayName) USER.display_name = b.display_name || b.displayName; if (b.email) USER.email = b.email; } catch { /* keep defaults */ }
    }
    return send(res, 200, { access_token: token(), refresh_token: "mock-refresh", expires_at: Date.now() + 3_600_000 });
  }
  if (p === "/auth/profile") {
    if (m === "PATCH") { try { const b = JSON.parse(body || "{}"); if (b.display_name || b.displayName) USER.display_name = b.display_name || b.displayName; } catch { /* ignore */ } }
    return send(res, 200, USER);
  }
  if (p === "/auth/logout") return send(res, 204, "");
  if (p.startsWith("/auth/users/")) return send(res, 200, { id: "u-2", email: "priya@thistlecombe.example", display_name: "Priya Ramanathan" });

  if (p === "/files" && m === "GET") {
    const folder = q.get("folder_id");
    return send(res, 200, page(FILES.filter((f) => (folder ? f.folder_id === folder : true)), q));
  }
  if (p === "/files/shared") return send(res, 200, page([FILES[0]], q));
  if (p === "/files/trash") return send(res, 200, page(TRASH, q));
  if (p === "/files/activity") {
    return send(res, 200, { items: [
      { id: "a-1", type: "upload", description: "uploaded", actor_name: USER.display_name, resource_name: FILES[1].name, resource_type: "file", resource_id: "f-2", created_at: now },
      { id: "a-2", type: "edit", description: "edited", actor_name: "Priya Ramanathan", resource_name: DOCS[0].title, resource_type: "document", resource_id: "doc-1", created_at: now },
    ] });
  }
  if (p === "/files/upload") return send(res, 201, { file: file(`f-${Date.now()}`, "upload.bin", "application/octet-stream", 1) });
  let mm;
  if ((mm = p.match(/^\/files\/([^/]+)\/download$/))) return send(res, 200, { url: `http://localhost:${PORT}/blob/${mm[1]}`, expires_in_secs: 300 });
  if ((mm = p.match(/^\/files\/([^/]+)$/)) && m === "GET") return send(res, 200, FILES.concat(TRASH).find((f) => f.id === mm[1]) || FILES[0]);
  if (p.startsWith("/files/")) return send(res, 200, {});
  if (p === "/folders" && m === "GET") return send(res, 200, { folders: FOLDERS.filter((f) => f.parent_id === (q.get("parent_id") || null)) });
  if ((mm = p.match(/^\/folders\/([^/]+)$/)) && m === "GET") return send(res, 200, FOLDERS.find((f) => f.id === mm[1]) || FOLDERS[0]);
  if (p.startsWith("/folders")) return send(res, 200, FOLDERS[0]);

  if (p === "/documents" && m === "GET") return send(res, 200, { data: DOCS, items: DOCS, total: DOCS.length, page: 1, page_size: 50, has_more: false });
  if (p === "/documents" && m === "POST") { const d = doc(`doc-${Date.now()}`, "Untitled", 0); DOCS.unshift(d); return send(res, 201, d); }
  if ((mm = p.match(/^\/documents\/([^/]+)$/))) return send(res, 200, DOCS.find((d) => d.id === mm[1]) || DOCS[0]);
  if (p.startsWith("/documents/")) return send(res, 200, {});

  if (p === "/search") {
    const term = (q.get("q") || "").toLowerCase();
    const results = [
      ...FILES.map((f) => ({ id: f.id, type: "file", title: f.name, content_snippet: "", updated_at: f.updated_at })),
      ...DOCS.map((d) => ({ id: d.id, type: "document", title: d.title, content_snippet: "Adjuster notes and photos", updated_at: d.updated_at })),
    ].filter((r) => r.title.toLowerCase().includes(term));
    return send(res, 200, { results, total: results.length, page: 1, page_size: 20 });
  }
  if (p === "/search/suggest") return send(res, 200, { suggestions: ["CLM-2026-100403", "POL-AUTO-48100"] });

  if (p === "/notifications/unread-count") return send(res, 200, { count: NOTIFS.filter((n) => !n.read).length });
  if (p === "/notifications") return send(res, 200, { data: NOTIFS, total: NOTIFS.length, page: 1, page_size: 20, has_more: false });
  if (p.startsWith("/notifications/")) return send(res, 204, "");

  if (p === "/settings") {
    if (m === "PATCH") { try { SETTINGS = { ...SETTINGS, ...Object.fromEntries(Object.entries(JSON.parse(body || "{}")).map(([k, v]) => [k.replace(/[A-Z]/g, (c) => `_${c.toLowerCase()}`), v])) }; } catch { /* ignore */ } }
    return send(res, 200, SETTINGS);
  }

  if (p === "/claims/fnol" && m === "POST") return handleFnol(body, res);
  if (p.startsWith("/blob/")) return send(res, 200, "mock file body", "text/plain");
  return send(res, 404, { error: "not_mocked", path: p });
}

createServer((req, res) => {
  const origin = String(req.headers.origin || "");
  if (LOCAL_ORIGIN.test(origin)) res.setHeader("Access-Control-Allow-Origin", origin);
  res.setHeader("Access-Control-Allow-Headers", "Authorization, Content-Type");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS");
  if (req.method === "OPTIONS") { res.writeHead(204); return res.end(); }
  let body = "";
  req.on("data", (c) => (body += c));
  req.on("end", () => {
    const ua = String(req.headers["user-agent"] || "");
    const client = ua.includes("OtterWorksApp/ios") ? "ios" : ua.includes("OtterWorksApp/android") ? "android" : "other";
    res.on("finish", () => console.log(`${new Date().toISOString()} ${client} ${req.method} ${req.url} -> ${res.statusCode}`));
    route(req, res, body);
  });
}).listen(PORT, () => console.log(`gateway mock listening on :${PORT}`));
