# collab-service: Node 24 Alpine digest-pinned base + apk upgrade

Scanner: Trivy 0.71.0, vulnerability DB v2 UpdatedAt 2026-11-13 12:56:33 UTC (same DB for before and after, `--skip-db-update`).

| image | Trivy ImageID | findings |
|---|---|---|
| before `collab-scan:baseline` | `sha256:bb0404e46d129f6224d220cb97ffdb4b7edfde145b8433e244327c4e8d414182` | total **165** (alpine 54, node-pkg 111); CRITICAL 4 / HIGH 73 / MEDIUM 49 / LOW 39 / UNKNOWN 0 |
| after `collab-scan:after` | `sha256:73a99bed6ec90817309dc883e23dbe726b434d25d0b50db41ec08a9ca7248e13` | total **91** (node-pkg 91); CRITICAL 3 / HIGH 51 / MEDIUM 32 / LOW 5 / UNKNOWN 0 |

Base images: before `node:20-alpine` (floating tag; resolved today to index `sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293`, Alpine 3.23.4, Node 20.20.2); after `node:24-alpine@sha256:116b800c3754b440ee0aa3ed2f20f5bf3d99a554bfd9adeea09ea8017f6e85f5` (Alpine 3.24.4 after `apk upgrade`, Node 24.22.3).

All five collab fixes applied together (base, prune, dep patches, drop npm, uuid 11) on this VM: total **4** (node-pkg 4); CRITICAL 0 / HIGH 1 / MEDIUM 3 / LOW 0 / UNKNOWN 0; image `sha256:035401a37b21dbbbb8503d30b6321df17bc27727cae8429953ebce423a985d7a`.

## Reproduce
```bash
# before: origin/demo-ciso; after: this branch
docker build -t collab-scan:<tag> services/collab-service
trivy image --scanners vuln --ignorefile /dev/null --severity UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL -f json -o <tag>.trivy.json collab-scan:<tag>
```
`before.trivy.json` / `after.trivy.json` are the scanner JSON reduced to ID, package, versions, severity and path (descriptions dropped). No ignore file or suppression was used.

## Records cleared (93)
| severity | ID | package | installed | path |
|---|---|---|---|---|
| CRITICAL | CVE-2026-59873 | tar | 6.2.1 | `usr/local/lib/node_modules/npm/node_modules/tar/package.json` |
| HIGH | CVE-2026-102276 | brace-expansion | 2.0.1 | `usr/local/lib/node_modules/npm/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-102278 | brace-expansion | 2.0.1 | `usr/local/lib/node_modules/npm/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-13149 | brace-expansion | 2.0.1 | `usr/local/lib/node_modules/npm/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-14257 | brace-expansion | 2.0.1 | `usr/local/lib/node_modules/npm/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-69152 | brace-expansion | 2.0.1 | `usr/local/lib/node_modules/npm/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2024-21538 | cross-spawn | 7.0.3 | `usr/local/lib/node_modules/npm/node_modules/cross-spawn/package.json` |
| HIGH | CVE-2025-64756 | glob | 10.4.2 | `usr/local/lib/node_modules/npm/node_modules/glob/package.json` |
| HIGH | CVE-2026-69192 | ip-address | 9.0.5 | `usr/local/lib/node_modules/npm/node_modules/ip-address/package.json` |
| HIGH | CVE-2026-14456 | libcrypto3 | 3.5.6-r0 | `os:alpine` |
| HIGH | CVE-2026-45447 | libcrypto3 | 3.5.6-r0 | `os:alpine` |
| HIGH | CVE-2026-14456 | libssl3 | 3.5.6-r0 | `os:alpine` |
| HIGH | CVE-2026-45447 | libssl3 | 3.5.6-r0 | `os:alpine` |
| HIGH | CVE-2026-26996 | minimatch | 9.0.5 | `usr/local/lib/node_modules/npm/node_modules/minimatch/package.json` |
| HIGH | CVE-2026-27903 | minimatch | 9.0.5 | `usr/local/lib/node_modules/npm/node_modules/minimatch/package.json` |
| HIGH | CVE-2026-27904 | minimatch | 9.0.5 | `usr/local/lib/node_modules/npm/node_modules/minimatch/package.json` |
| HIGH | CVE-2026-107891 | musl | 1.2.5-r23 | `os:alpine` |
| HIGH | CVE-2026-107891 | musl-utils | 1.2.5-r23 | `os:alpine` |
| HIGH | CVE-2026-9496 | pacote | 18.0.6 | `usr/local/lib/node_modules/npm/node_modules/pacote/package.json` |
| HIGH | CVE-2026-48815 | sigstore | 2.3.1 | `usr/local/lib/node_modules/npm/node_modules/sigstore/package.json` |
| HIGH | CVE-2026-23745 | tar | 6.2.1 | `usr/local/lib/node_modules/npm/node_modules/tar/package.json` |
| HIGH | CVE-2026-23950 | tar | 6.2.1 | `usr/local/lib/node_modules/npm/node_modules/tar/package.json` |
| HIGH | CVE-2026-24842 | tar | 6.2.1 | `usr/local/lib/node_modules/npm/node_modules/tar/package.json` |
| HIGH | CVE-2026-26960 | tar | 6.2.1 | `usr/local/lib/node_modules/npm/node_modules/tar/package.json` |
| HIGH | CVE-2026-29786 | tar | 6.2.1 | `usr/local/lib/node_modules/npm/node_modules/tar/package.json` |
| HIGH | CVE-2026-31802 | tar | 6.2.1 | `usr/local/lib/node_modules/npm/node_modules/tar/package.json` |
| HIGH | CVE-2026-59874 | tar | 6.2.1 | `usr/local/lib/node_modules/npm/node_modules/tar/package.json` |
| HIGH | CVE-2026-73566 | tar | 6.2.1 | `usr/local/lib/node_modules/npm/node_modules/tar/package.json` |
| HIGH | CVE-2026-85091 | zlib | 1.3.2-r0 | `os:alpine` |
| MEDIUM | CVE-2026-48758 | @sigstore/core | 1.1.0 | `usr/local/lib/node_modules/npm/node_modules/@sigstore/core/package.json` |
| MEDIUM | CVE-2026-102277 | brace-expansion | 2.0.1 | `usr/local/lib/node_modules/npm/node_modules/brace-expansion/package.json` |
| MEDIUM | CVE-2026-33750 | brace-expansion | 2.0.1 | `usr/local/lib/node_modules/npm/node_modules/brace-expansion/package.json` |
| MEDIUM | CVE-2026-118773 | glob | 10.4.2 | `usr/local/lib/node_modules/npm/node_modules/glob/package.json` |
| MEDIUM | CVE-2026-101911 | ip-address | 9.0.5 | `usr/local/lib/node_modules/npm/node_modules/ip-address/package.json` |
| MEDIUM | CVE-2026-101912 | ip-address | 9.0.5 | `usr/local/lib/node_modules/npm/node_modules/ip-address/package.json` |
| MEDIUM | CVE-2026-101913 | ip-address | 9.0.5 | `usr/local/lib/node_modules/npm/node_modules/ip-address/package.json` |
| MEDIUM | CVE-2026-111997 | ip-address | 9.0.5 | `usr/local/lib/node_modules/npm/node_modules/ip-address/package.json` |
| MEDIUM | CVE-2026-42338 | ip-address | 9.0.5 | `usr/local/lib/node_modules/npm/node_modules/ip-address/package.json` |
| MEDIUM | CVE-2026-18798 | libcrypto3 | 3.5.6-r0 | `os:alpine` |
| MEDIUM | CVE-2026-34182 | libcrypto3 | 3.5.6-r0 | `os:alpine` |
| MEDIUM | CVE-2026-34183 | libcrypto3 | 3.5.6-r0 | `os:alpine` |
| MEDIUM | CVE-2026-42764 | libcrypto3 | 3.5.6-r0 | `os:alpine` |
| MEDIUM | CVE-2026-45445 | libcrypto3 | 3.5.6-r0 | `os:alpine` |
| MEDIUM | CVE-2026-63072 | libcrypto3 | 3.5.6-r0 | `os:alpine` |
| MEDIUM | CVE-2026-63076 | libcrypto3 | 3.5.6-r0 | `os:alpine` |
| MEDIUM | CVE-2026-18798 | libssl3 | 3.5.6-r0 | `os:alpine` |
| MEDIUM | CVE-2026-34182 | libssl3 | 3.5.6-r0 | `os:alpine` |
| MEDIUM | CVE-2026-34183 | libssl3 | 3.5.6-r0 | `os:alpine` |
| MEDIUM | CVE-2026-42764 | libssl3 | 3.5.6-r0 | `os:alpine` |
| MEDIUM | CVE-2026-45445 | libssl3 | 3.5.6-r0 | `os:alpine` |
| MEDIUM | CVE-2026-63072 | libssl3 | 3.5.6-r0 | `os:alpine` |
| MEDIUM | CVE-2026-63076 | libssl3 | 3.5.6-r0 | `os:alpine` |
| MEDIUM | CVE-2026-118764 | minimatch | 9.0.5 | `usr/local/lib/node_modules/npm/node_modules/minimatch/package.json` |
| MEDIUM | CVE-2026-104844 | postcss-selector-parser | 6.1.0 | `usr/local/lib/node_modules/npm/node_modules/postcss-selector-parser/package.json` |
| MEDIUM | CVE-2026-53655 | tar | 6.2.1 | `usr/local/lib/node_modules/npm/node_modules/tar/package.json` |
| MEDIUM | CVE-2026-59871 | tar | 6.2.1 | `usr/local/lib/node_modules/npm/node_modules/tar/package.json` |
| MEDIUM | CVE-2026-59875 | tar | 6.2.1 | `usr/local/lib/node_modules/npm/node_modules/tar/package.json` |
| MEDIUM | CVE-2026-4738 | zlib | 1.3.2-r0 | `os:alpine` |
| LOW | CVE-2025-5889 | brace-expansion | 2.0.1 | `usr/local/lib/node_modules/npm/node_modules/brace-expansion/package.json` |
| LOW | CVE-2026-24001 | diff | 5.2.0 | `usr/local/lib/node_modules/npm/node_modules/diff/package.json` |
| LOW | CVE-2026-14457 | libcrypto3 | 3.5.6-r0 | `os:alpine` |
| LOW | CVE-2026-34180 | libcrypto3 | 3.5.6-r0 | `os:alpine` |
| LOW | CVE-2026-34181 | libcrypto3 | 3.5.6-r0 | `os:alpine` |
| LOW | CVE-2026-42766 | libcrypto3 | 3.5.6-r0 | `os:alpine` |
| LOW | CVE-2026-42767 | libcrypto3 | 3.5.6-r0 | `os:alpine` |
| LOW | CVE-2026-42768 | libcrypto3 | 3.5.6-r0 | `os:alpine` |
| LOW | CVE-2026-42769 | libcrypto3 | 3.5.6-r0 | `os:alpine` |
| LOW | CVE-2026-42770 | libcrypto3 | 3.5.6-r0 | `os:alpine` |
| LOW | CVE-2026-45446 | libcrypto3 | 3.5.6-r0 | `os:alpine` |
| LOW | CVE-2026-54874 | libcrypto3 | 3.5.6-r0 | `os:alpine` |
| LOW | CVE-2026-63073 | libcrypto3 | 3.5.6-r0 | `os:alpine` |
| LOW | CVE-2026-63074 | libcrypto3 | 3.5.6-r0 | `os:alpine` |
| LOW | CVE-2026-63075 | libcrypto3 | 3.5.6-r0 | `os:alpine` |
| LOW | CVE-2026-7383 | libcrypto3 | 3.5.6-r0 | `os:alpine` |
| LOW | CVE-2026-75803 | libcrypto3 | 3.5.6-r0 | `os:alpine` |
| LOW | CVE-2026-9076 | libcrypto3 | 3.5.6-r0 | `os:alpine` |
| LOW | CVE-2026-14457 | libssl3 | 3.5.6-r0 | `os:alpine` |
| LOW | CVE-2026-34180 | libssl3 | 3.5.6-r0 | `os:alpine` |
| LOW | CVE-2026-34181 | libssl3 | 3.5.6-r0 | `os:alpine` |
| LOW | CVE-2026-42766 | libssl3 | 3.5.6-r0 | `os:alpine` |
| LOW | CVE-2026-42767 | libssl3 | 3.5.6-r0 | `os:alpine` |
| LOW | CVE-2026-42768 | libssl3 | 3.5.6-r0 | `os:alpine` |
| LOW | CVE-2026-42769 | libssl3 | 3.5.6-r0 | `os:alpine` |
| LOW | CVE-2026-42770 | libssl3 | 3.5.6-r0 | `os:alpine` |
| LOW | CVE-2026-45446 | libssl3 | 3.5.6-r0 | `os:alpine` |
| LOW | CVE-2026-54874 | libssl3 | 3.5.6-r0 | `os:alpine` |
| LOW | CVE-2026-63073 | libssl3 | 3.5.6-r0 | `os:alpine` |
| LOW | CVE-2026-63074 | libssl3 | 3.5.6-r0 | `os:alpine` |
| LOW | CVE-2026-63075 | libssl3 | 3.5.6-r0 | `os:alpine` |
| LOW | CVE-2026-7383 | libssl3 | 3.5.6-r0 | `os:alpine` |
| LOW | CVE-2026-75803 | libssl3 | 3.5.6-r0 | `os:alpine` |
| LOW | CVE-2026-9076 | libssl3 | 3.5.6-r0 | `os:alpine` |
| LOW | CVE-2026-9358 | postcss-selector-parser | 6.1.0 | `usr/local/lib/node_modules/npm/node_modules/postcss-selector-parser/package.json` |

## Records introduced (19)
| severity | ID | package | installed | path |
|---|---|---|---|---|
| HIGH | CVE-2026-102276 | brace-expansion | 5.0.9 | `usr/local/lib/node_modules/npm/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-102278 | brace-expansion | 5.0.9 | `usr/local/lib/node_modules/npm/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-109383 | undici | 6.28.0 | `usr/local/lib/node_modules/npm/node_modules/undici/package.json` |
| HIGH | CVE-2026-109869 | undici | 6.28.0 | `usr/local/lib/node_modules/npm/node_modules/undici/package.json` |
| HIGH | CVE-2026-19534 | undici | 6.28.0 | `usr/local/lib/node_modules/npm/node_modules/undici/package.json` |
| HIGH | CVE-2026-87018 | undici | 6.28.0 | `usr/local/lib/node_modules/npm/node_modules/undici/package.json` |
| MEDIUM | CVE-2026-102277 | brace-expansion | 5.0.9 | `usr/local/lib/node_modules/npm/node_modules/brace-expansion/package.json` |
| MEDIUM | CVE-2026-118773 | glob | 13.0.6 | `usr/local/lib/node_modules/npm/node_modules/glob/package.json` |
| MEDIUM | CVE-2026-101910 | ip-address | 10.5.0 | `usr/local/lib/node_modules/npm/node_modules/ip-address/package.json` |
| MEDIUM | CVE-2026-101911 | ip-address | 10.5.0 | `usr/local/lib/node_modules/npm/node_modules/ip-address/package.json` |
| MEDIUM | CVE-2026-101912 | ip-address | 10.5.0 | `usr/local/lib/node_modules/npm/node_modules/ip-address/package.json` |
| MEDIUM | CVE-2026-101913 | ip-address | 10.5.0 | `usr/local/lib/node_modules/npm/node_modules/ip-address/package.json` |
| MEDIUM | CVE-2026-111997 | ip-address | 10.5.0 | `usr/local/lib/node_modules/npm/node_modules/ip-address/package.json` |
| MEDIUM | CVE-2026-118764 | minimatch | 10.2.5 | `usr/local/lib/node_modules/npm/node_modules/minimatch/package.json` |
| MEDIUM | CVE-2026-104844 | postcss-selector-parser | 7.1.4 | `usr/local/lib/node_modules/npm/node_modules/postcss-selector-parser/package.json` |
| MEDIUM | CVE-2026-109924 | undici | 6.28.0 | `usr/local/lib/node_modules/npm/node_modules/undici/package.json` |
| MEDIUM | CVE-2026-109932 | undici | 6.28.0 | `usr/local/lib/node_modules/npm/node_modules/undici/package.json` |
| MEDIUM | CVE-2026-85024 | undici | 6.28.0 | `usr/local/lib/node_modules/npm/node_modules/undici/package.json` |
| LOW | CVE-2026-18540 | undici | 6.28.0 | `usr/local/lib/node_modules/npm/node_modules/undici/package.json` |

## Residual in after image (91)
| severity | ID | package | installed | fixed in | path |
|---|---|---|---|---|---|
| CRITICAL | CVE-2026-106445 | handlebars | 4.7.9 | 4.7.10 | `app/node_modules/handlebars/package.json` |
| CRITICAL | CVE-2026-106446 | handlebars | 4.7.9 | 4.7.10 | `app/node_modules/handlebars/package.json` |
| CRITICAL | CVE-2026-90711 | proxy-addr | 2.0.7 | 2.0.8 | `app/node_modules/proxy-addr/package.json` |
| HIGH | CVE-2026-101916 | @grpc/grpc-js | 1.14.4 | 1.13.6, 1.14.5 | `app/node_modules/@grpc/grpc-js/package.json` |
| HIGH | CVE-2026-59892 | @opentelemetry/propagator-jaeger | 1.22.0 | 2.9.0 | `app/node_modules/@opentelemetry/propagator-jaeger/package.json` |
| HIGH | CVE-2026-111181 | body-parser | 1.20.4 | 2.4.0, 1.20.9 | `app/node_modules/body-parser/package.json` |
| HIGH | CVE-2026-102276 | brace-expansion | 1.1.14 | 5.0.10, 3.0.7, 2.1.5, 1.1.19 | `app/node_modules/@eslint/eslintrc/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-102276 | brace-expansion | 1.1.14 | 5.0.10, 3.0.7, 2.1.5, 1.1.19 | `app/node_modules/@humanwhocodes/config-array/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-102276 | brace-expansion | 1.1.14 | 5.0.10, 3.0.7, 2.1.5, 1.1.19 | `app/node_modules/eslint/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-102276 | brace-expansion | 1.1.14 | 5.0.10, 3.0.7, 2.1.5, 1.1.19 | `app/node_modules/glob/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-102276 | brace-expansion | 1.1.14 | 5.0.10, 3.0.7, 2.1.5, 1.1.19 | `app/node_modules/test-exclude/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-102278 | brace-expansion | 1.1.14 | 5.0.11, 3.0.8, 2.1.6, 1.1.20 | `app/node_modules/@eslint/eslintrc/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-102278 | brace-expansion | 1.1.14 | 5.0.11, 3.0.8, 2.1.6, 1.1.20 | `app/node_modules/@humanwhocodes/config-array/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-102278 | brace-expansion | 1.1.14 | 5.0.11, 3.0.8, 2.1.6, 1.1.20 | `app/node_modules/eslint/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-102278 | brace-expansion | 1.1.14 | 5.0.11, 3.0.8, 2.1.6, 1.1.20 | `app/node_modules/glob/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-102278 | brace-expansion | 1.1.14 | 5.0.11, 3.0.8, 2.1.6, 1.1.20 | `app/node_modules/test-exclude/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-13149 | brace-expansion | 1.1.14 | 5.0.7, 1.1.16, 2.1.2 | `app/node_modules/@eslint/eslintrc/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-13149 | brace-expansion | 1.1.14 | 5.0.7, 1.1.16, 2.1.2 | `app/node_modules/@humanwhocodes/config-array/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-13149 | brace-expansion | 1.1.14 | 5.0.7, 1.1.16, 2.1.2 | `app/node_modules/eslint/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-13149 | brace-expansion | 1.1.14 | 5.0.7, 1.1.16, 2.1.2 | `app/node_modules/glob/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-13149 | brace-expansion | 1.1.14 | 5.0.7, 1.1.16, 2.1.2 | `app/node_modules/test-exclude/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-14257 | brace-expansion | 1.1.14 | 5.0.8, 3.0.3, 2.1.3, 1.1.17 | `app/node_modules/@eslint/eslintrc/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-14257 | brace-expansion | 1.1.14 | 5.0.8, 3.0.3, 2.1.3, 1.1.17 | `app/node_modules/@humanwhocodes/config-array/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-14257 | brace-expansion | 1.1.14 | 5.0.8, 3.0.3, 2.1.3, 1.1.17 | `app/node_modules/eslint/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-14257 | brace-expansion | 1.1.14 | 5.0.8, 3.0.3, 2.1.3, 1.1.17 | `app/node_modules/glob/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-14257 | brace-expansion | 1.1.14 | 5.0.8, 3.0.3, 2.1.3, 1.1.17 | `app/node_modules/test-exclude/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-69152 | brace-expansion | 1.1.14 | 1.1.18, 2.1.4, 3.0.6, 5.0.9 | `app/node_modules/@eslint/eslintrc/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-69152 | brace-expansion | 1.1.14 | 1.1.18, 2.1.4, 3.0.6, 5.0.9 | `app/node_modules/@humanwhocodes/config-array/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-69152 | brace-expansion | 1.1.14 | 1.1.18, 2.1.4, 3.0.6, 5.0.9 | `app/node_modules/eslint/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-69152 | brace-expansion | 1.1.14 | 1.1.18, 2.1.4, 3.0.6, 5.0.9 | `app/node_modules/glob/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-69152 | brace-expansion | 1.1.14 | 1.1.18, 2.1.4, 3.0.6, 5.0.9 | `app/node_modules/test-exclude/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-102276 | brace-expansion | 2.1.0 | 5.0.10, 3.0.7, 2.1.5, 1.1.19 | `app/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-102278 | brace-expansion | 2.1.0 | 5.0.11, 3.0.8, 2.1.6, 1.1.20 | `app/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-13149 | brace-expansion | 2.1.0 | 5.0.7, 1.1.16, 2.1.2 | `app/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-14257 | brace-expansion | 2.1.0 | 5.0.8, 3.0.3, 2.1.3, 1.1.17 | `app/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-69152 | brace-expansion | 2.1.0 | 1.1.18, 2.1.4, 3.0.6, 5.0.9 | `app/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-102276 | brace-expansion | 5.0.9 | 5.0.10, 3.0.7, 2.1.5, 1.1.19 | `usr/local/lib/node_modules/npm/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-102278 | brace-expansion | 5.0.9 | 5.0.11, 3.0.8, 2.1.6, 1.1.20 | `usr/local/lib/node_modules/npm/node_modules/brace-expansion/package.json` |
| HIGH | CVE-2026-73088 | browserslist | 4.28.2 | 4.28.7 | `app/node_modules/browserslist/package.json` |
| HIGH | CVE-2026-73089 | browserslist | 4.28.2 | 4.28.7 | `app/node_modules/browserslist/package.json` |
| HIGH | CVE-2026-102599 | engine.io | 6.6.6 | 6.6.10 | `app/node_modules/engine.io/package.json` |
| HIGH | CVE-2026-59724 | engine.io | 6.6.6 | 6.6.7 | `app/node_modules/engine.io/package.json` |
| HIGH | CVE-2026-59725 | engine.io | 6.6.6 | 6.6.7 | `app/node_modules/engine.io/package.json` |
| HIGH | CVE-2026-59869 | js-yaml | 3.14.2 | 3.15.0, 4.3.0 | `app/node_modules/@istanbuljs/load-nyc-config/node_modules/js-yaml/package.json` |
| HIGH | CVE-2026-84375 | js-yaml | 3.14.2 | 4.3.2, 3.15.2 | `app/node_modules/@istanbuljs/load-nyc-config/node_modules/js-yaml/package.json` |
| HIGH | GHSA-5p4m-2wfm-xmqj | js-yaml | 3.14.2 | 4.3.1, 3.15.1 | `app/node_modules/@istanbuljs/load-nyc-config/node_modules/js-yaml/package.json` |
| HIGH | CVE-2026-59869 | js-yaml | 4.1.1 | 3.15.0, 4.3.0 | `app/node_modules/js-yaml/package.json` |
| HIGH | CVE-2026-84375 | js-yaml | 4.1.1 | 4.3.2, 3.15.2 | `app/node_modules/js-yaml/package.json` |
| HIGH | GHSA-5p4m-2wfm-xmqj | js-yaml | 4.1.1 | 4.3.1, 3.15.1 | `app/node_modules/js-yaml/package.json` |
| HIGH | CVE-2026-69185 | socket.io-parser | 4.2.6 | 4.2.7, 3.4.5, 3.3.6 | `app/node_modules/socket.io-parser/package.json` |
| HIGH | CVE-2026-109383 | undici | 6.28.0 | 6.29.1, 7.30.1, 8.12.2 | `usr/local/lib/node_modules/npm/node_modules/undici/package.json` |
| HIGH | CVE-2026-109869 | undici | 6.28.0 | 6.29.1, 7.30.1, 8.12.2 | `usr/local/lib/node_modules/npm/node_modules/undici/package.json` |
| HIGH | CVE-2026-19534 | undici | 6.28.0 | 6.28.1, 7.29.1, 8.10.2 | `usr/local/lib/node_modules/npm/node_modules/undici/package.json` |
| HIGH | CVE-2026-87018 | undici | 6.28.0 | 6.29.1, 7.30.1, 8.12.2 | `usr/local/lib/node_modules/npm/node_modules/undici/package.json` |
| MEDIUM | CVE-2026-54285 | @opentelemetry/core | 1.22.0 | 2.8.0 | `app/node_modules/@opentelemetry/core/package.json` |
| MEDIUM | CVE-2026-54285 | @opentelemetry/core | 1.30.1 | 2.8.0 | `app/node_modules/@opentelemetry/resources/node_modules/@opentelemetry/core/package.json` |
| MEDIUM | CVE-2026-54285 | @opentelemetry/core | 1.30.1 | 2.8.0 | `app/node_modules/@opentelemetry/sdk-trace-base/node_modules/@opentelemetry/core/package.json` |
| MEDIUM | CVE-2026-45819 | baseline-browser-mapping | 2.10.19 | 2.11.0 | `app/node_modules/baseline-browser-mapping/package.json` |
| MEDIUM | CVE-2026-102277 | brace-expansion | 1.1.14 | 5.0.12, 3.0.9, 2.1.7, 1.1.21 | `app/node_modules/@eslint/eslintrc/node_modules/brace-expansion/package.json` |
| MEDIUM | CVE-2026-102277 | brace-expansion | 1.1.14 | 5.0.12, 3.0.9, 2.1.7, 1.1.21 | `app/node_modules/@humanwhocodes/config-array/node_modules/brace-expansion/package.json` |
| MEDIUM | CVE-2026-102277 | brace-expansion | 1.1.14 | 5.0.12, 3.0.9, 2.1.7, 1.1.21 | `app/node_modules/eslint/node_modules/brace-expansion/package.json` |
| MEDIUM | CVE-2026-102277 | brace-expansion | 1.1.14 | 5.0.12, 3.0.9, 2.1.7, 1.1.21 | `app/node_modules/glob/node_modules/brace-expansion/package.json` |
| MEDIUM | CVE-2026-102277 | brace-expansion | 1.1.14 | 5.0.12, 3.0.9, 2.1.7, 1.1.21 | `app/node_modules/test-exclude/node_modules/brace-expansion/package.json` |
| MEDIUM | CVE-2026-102277 | brace-expansion | 2.1.0 | 5.0.12, 3.0.9, 2.1.7, 1.1.21 | `app/node_modules/brace-expansion/package.json` |
| MEDIUM | CVE-2026-102277 | brace-expansion | 5.0.9 | 5.0.12, 3.0.9, 2.1.7, 1.1.21 | `usr/local/lib/node_modules/npm/node_modules/brace-expansion/package.json` |
| MEDIUM | GHSA-jggr-w7fw-pc2j | fast-copy | 3.0.2 | 4.1.0, 3.1.0, 2.2.0 | `app/node_modules/fast-copy/package.json` |
| MEDIUM | CVE-2026-118773 | glob | 13.0.6 | 14.0.2 | `usr/local/lib/node_modules/npm/node_modules/glob/package.json` |
| MEDIUM | CVE-2026-106444 | handlebars | 4.7.9 | 4.7.10 | `app/node_modules/handlebars/package.json` |
| MEDIUM | CVE-2026-101910 | ip-address | 10.5.0 | 10.5.1 | `usr/local/lib/node_modules/npm/node_modules/ip-address/package.json` |
| MEDIUM | CVE-2026-101911 | ip-address | 10.5.0 | 10.7.1 | `usr/local/lib/node_modules/npm/node_modules/ip-address/package.json` |
| MEDIUM | CVE-2026-101912 | ip-address | 10.5.0 | 10.7.1 | `usr/local/lib/node_modules/npm/node_modules/ip-address/package.json` |
| MEDIUM | CVE-2026-101913 | ip-address | 10.5.0 | 10.5.1 | `usr/local/lib/node_modules/npm/node_modules/ip-address/package.json` |
| MEDIUM | CVE-2026-111997 | ip-address | 10.5.0 | 10.7.4 | `usr/local/lib/node_modules/npm/node_modules/ip-address/package.json` |
| MEDIUM | CVE-2026-53550 | js-yaml | 3.14.2 | 4.2.0, 3.15.0 | `app/node_modules/@istanbuljs/load-nyc-config/node_modules/js-yaml/package.json` |
| MEDIUM | CVE-2026-53550 | js-yaml | 4.1.1 | 4.2.0, 3.15.0 | `app/node_modules/js-yaml/package.json` |
| MEDIUM | CVE-2026-118764 | minimatch | 10.2.5 | 11.0.1 | `usr/local/lib/node_modules/npm/node_modules/minimatch/package.json` |
| MEDIUM | CVE-2026-118764 | minimatch | 9.0.9 | 11.0.1 | `app/node_modules/minimatch/package.json` |
| MEDIUM | CVE-2026-104844 | postcss-selector-parser | 7.1.4 | 7.1.6, 6.1.5 | `usr/local/lib/node_modules/npm/node_modules/postcss-selector-parser/package.json` |
| MEDIUM | CVE-2026-110816 | qs | 6.14.2 | 6.16.1 | `app/node_modules/qs/package.json` |
| MEDIUM | CVE-2026-82417 | qs | 6.14.2 | 6.16.0 | `app/node_modules/qs/package.json` |
| MEDIUM | CVE-2026-82562 | qs | 6.14.2 | 6.16.0 | `app/node_modules/qs/package.json` |
| MEDIUM | CVE-2026-8723 | qs | 6.14.2 | 6.15.2 | `app/node_modules/qs/package.json` |
| MEDIUM | CVE-2026-109924 | undici | 6.28.0 | 6.29.1, 7.30.1, 8.12.2 | `usr/local/lib/node_modules/npm/node_modules/undici/package.json` |
| MEDIUM | CVE-2026-109932 | undici | 6.28.0 | 6.29.1, 7.30.1, 8.12.2 | `usr/local/lib/node_modules/npm/node_modules/undici/package.json` |
| MEDIUM | CVE-2026-85024 | undici | 6.28.0 | 6.28.1, 7.29.1, 8.10.2 | `usr/local/lib/node_modules/npm/node_modules/undici/package.json` |
| MEDIUM | CVE-2026-41907 | uuid | 9.0.1 | 11.1.1, 12.0.1, 13.0.1 | `app/node_modules/uuid/package.json` |
| LOW | CVE-2026-49356 | @babel/core | 7.29.0 | 8.0.0-rc.6, 7.29.6 | `app/node_modules/@babel/core/package.json` |
| LOW | CVE-2026-101915 | @grpc/grpc-js | 1.14.4 | 1.13.6, 1.14.5 | `app/node_modules/@grpc/grpc-js/package.json` |
| LOW | CVE-2026-12590 | body-parser | 1.20.4 | 1.20.6, 2.3.0 | `app/node_modules/body-parser/package.json` |
| LOW | GHSA-g7r4-m6w7-qqqr | esbuild | 0.27.7 | 0.28.1 | `app/node_modules/esbuild/package.json` |
| LOW | CVE-2026-18540 | undici | 6.28.0 | 6.28.1, 7.29.1, 8.10.2 | `usr/local/lib/node_modules/npm/node_modules/undici/package.json` |
