# api-gateway third-party Go modules (Go 1.22-compatible bumps)

Locally built images from `demo-ciso` (`services/api-gateway/Dockerfile`, unchanged). Not the deployed ECR image.

```sh
cd services/api-gateway
docker build -t ow-gw:baseline .          # before (demo-ciso)
docker build -t ow-gw:deps-a .            # after (this branch)
trivy image --image-src docker --scanners vuln --ignorefile /dev/null --no-progress \
  --format json --output deps-a.json ow-gw:deps-a
```

All severities, no ignore file, no suppressions. `trivy-*.json` are the raw Trivy JSON reports
reduced to identifiers (ID, package, installed/fixed version, severity); `summary-*.txt` are the
counts. Scanner version and DB timestamp: `trivy-version.txt`.

| Scope | Before | After |
|---|---:|---:|
| Go third-party module records | 39 | 36 |
| Full image records | 155 | 152 |

Before ImageID `sha256:bd9d8d4a75d073cad804673b8b4e725b0309b7194e82d4de1ba6f82f690ec0bf`,
after ImageID `sha256:f58ae147eee795cf97b56501034e344242c497d2262a9972fc54492a6878f81a`.
