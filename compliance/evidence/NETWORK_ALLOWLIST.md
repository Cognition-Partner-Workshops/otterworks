# Weekly evidence download destinations

This is a service-level allowlist, not a claim that a single run contacts every
entry. Caches avoid downloads. Registries, GitHub artifacts and release assets use
redirects to regional or dynamically named storage hosts; a fixed exhaustive list
of individual hostnames cannot be guaranteed. Allow HTTPS (443), and HTTP (80)
for this machine's Ubuntu apt sources. Recheck configured apt sources, Maven/Gradle
repositories, scanner defaults and image registries when changing the environment.

| Purpose | Hostnames / required storage families |
| --- | --- |
| Ubuntu apt mirrors on this host | `archive.ubuntu.com`, `security.ubuntu.com` |
| Other configured apt sources contacted by apt update | `download.docker.com`, `ppa.launchpadcontent.net` |
| Conditional Temurin apt repository/key | `packages.adoptium.net` |
| Pinned Gradle distribution/checksum and redirects | `downloads.gradle.org`, `services.gradle.org` (module wrapper), `github.com`, `release-assets.githubusercontent.com` |
| Maven Central dependencies and Maven wrapper distribution | `repo.maven.apache.org`, `repo1.maven.org` (official alternate, not automatically selected) |
| Gradle plugin resolution | `plugins.gradle.org`, `plugins-artifacts.gradle.org`, Maven Central hosts |
| Optional operator-specified mirror | Host and redirect destinations in `MAVEN_MIRROR_URL`; unset by default |
| Python provisioning, harness dependencies, remote Sonar job test dependencies | `pypi.org`, `files.pythonhosted.org`; also any operator-configured pip/uv index |
| Scanner releases, source clones, GitHub API | `github.com`, `api.github.com`, `release-assets.githubusercontent.com`, `codeload.github.com`, `objects.githubusercontent.com` |
| Trivy vulnerability and Java DB defaults, including fallback | `mirror.gcr.io`, `ghcr.io`, `pkg-containers.githubusercontent.com`; Google registry storage redirects may require `storage.googleapis.com` |
| Docker Hub runtime images and remote Sonar containers | `registry-1.docker.io`, `auth.docker.io`, `production.cloudflare.docker.com`, `production.cloudfront.docker.com`, `*.r2.cloudflarestorage.com` |
| Microsoft .NET runtime image | `mcr.microsoft.com`, `*.data.mcr.microsoft.com` |
| GitHub Actions artifact download/control and remote job storage | `*.actions.githubusercontent.com`, `*.blob.core.windows.net`, `results-receiver.actions.githubusercontent.com` |

The Sonar job starts a local SonarQube server and scanner container. It does not
require SonarCloud. Its GitHub clones, Docker pulls and pip installs happen on the
GitHub runner, not this host. Actions themselves additionally use GitHub's managed
runner networking; consult GitHub's current Actions runner allowlist for an
enterprise self-hosted replacement. OS package post-install hooks, custom mirrors,
proxy deployments and future image/CDN redirects can add destinations.

Observed here: apt used the four configured apt hosts above; Gradle 8.6 downloaded
successfully through GitHub release assets. Both Maven Central hostnames returned
HTTP 429. The downloaded banking artifact redirects to
`productionresultssa12.blob.core.windows.net` (the storage account can change).
Trivy 0.71.0 reports `mirror.gcr.io` then `ghcr.io` as its default DB
repository order. Storage wildcard entries are conditional service requirements,
not an assertion that all were observed in this run.
