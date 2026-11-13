# api-gateway third-party Go modules (full upgrade; requires Go 1.26 builder)

Builds only with the Go 1.26 builder from the separate toolchain PR (#2858). With the
`golang:1.22-alpine` builder on `demo-ciso`, `go mod download` fails because the upgraded
modules declare `go 1.25`/`go 1.26`. Locally built images; not the deployed ECR image.

```sh
cd services/api-gateway
# Dockerfile.go126 = services/api-gateway/Dockerfile from the #2858 branch (Go 1.26.11 builder digest)
docker build -t ow-gw:baseline .                                  # demo-ciso as-is
docker build -f Dockerfile.go126 -t ow-gw:toolchain-only .        # demo-ciso go.mod + #2858 builder
docker build -f Dockerfile.go126 -t ow-gw:deps-b-go126 .          # this branch go.mod + #2858 builder
trivy image --image-src docker --scanners vuln --ignorefile /dev/null --no-progress \
  --format json --output deps-b-go126.json ow-gw:deps-b-go126
```

All severities, no ignore file, no suppressions. `trivy-*.json` are the raw Trivy JSON reports
reduced to identifiers; `summary-*.txt` are the counts; `trivy-version.txt` has the scanner and DB.

| Scope | demo-ciso | toolchain only (#2858) | toolchain + this PR |
|---|---:|---:|---:|
| Go third-party module records | 39 | 39 | 0 |
| Go stdlib records | 67 | 0 | 0 |
| Full image records | 155 | 88 | 49 (all Alpine 3.18 OS, owned by #2859) |

ImageIDs: baseline `sha256:bd9d8d4a75d073cad804673b8b4e725b0309b7194e82d4de1ba6f82f690ec0bf`,
toolchain-only `sha256:05436088435aa31d9f73baff1ecf1fbfd44c48f5d1e9f844e9ae0cfc7f9e0a44`,
after `sha256:6ad85ee087f04a5d6c1b35edc8638ed5fbbedc1f02a88a0ec48ff08c7c34e4fe`.
