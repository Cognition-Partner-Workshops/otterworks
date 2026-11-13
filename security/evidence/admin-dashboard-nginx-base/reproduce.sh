#!/usr/bin/env bash
# Frontend image evidence run: build demo-ciso (before) and fix branches (after), Trivy all severities, no suppressions.
set -uo pipefail
export TRIVY_CACHE_DIR=$HOME/fe/trivy-cache
E=$HOME/fe/evidence
T="trivy --cache-dir $TRIVY_CACHE_DIR --skip-db-update --quiet"
OPTS="--scanners vuln --ignorefile /dev/null"
counts() { jq -r '[.Results[]?.Vulnerabilities[]?|.Severity] as $s | "CRITICAL=\([$s[]|select(.=="CRITICAL")]|length) HIGH=\([$s[]|select(.=="HIGH")]|length) MEDIUM=\([$s[]|select(.=="MEDIUM")]|length) LOW=\([$s[]|select(.=="LOW")]|length) UNKNOWN=\([$s[]|select(.=="UNKNOWN")]|length) total=\($s|length)"' "$1"; }
compact() { jq '{ArtifactName,ImageID:.Metadata.ImageID,RepoDigests:.Metadata.RepoDigests,OS:.Metadata.OS,Results:[.Results[]?|{Target,Class,Type,Vulnerabilities:[.Vulnerabilities[]?|{VulnerabilityID,PkgName,InstalledVersion,FixedVersion,Status,Severity}]}]}' "$1"; }
hdr() { printf '\n\033[1;36m==== %s ====\033[0m\n' "$*"; }
hdr "Tool + DB versions"; trivy --version --cache-dir $TRIVY_CACHE_DIR | tee $E/trivy-version.txt
img() { # fix name tag ctxdir
  local fix=$1 name=$2 tag=$3 ctx=$4; local d=$E/$fix; mkdir -p $d
  hdr "$fix: docker build $name:$tag from $ctx"
  docker build -q -t ow-fe/$name:$tag $ctx | tee $d/$tag-image-id.txt
  $T image $OPTS --format json --output /tmp/$fix-$tag.json ow-fe/$name:$tag
  compact /tmp/$fix-$tag.json > $d/trivy-$tag.json
  $T image $OPTS --format table ow-fe/$name:$tag > $d/trivy-$tag.txt
  echo "$tag $(jq -r '"\(.Metadata.OS.Family) \(.Metadata.OS.Name) EOSL=\(.Metadata.OS.EOSL // false)"' /tmp/$fix-$tag.json) $(counts /tmp/$fix-$tag.json)" | tee -a $d/summary.txt
  grep -E "^(Report Summary|│|Total:)" -m 12 $d/trivy-$tag.txt | head -12
}
: > $E/web-app-nginx-base/summary.txt 2>/dev/null; : > $E/admin-dashboard-nginx-base/summary.txt 2>/dev/null; : > $E/web-app-npm-deps/summary.txt 2>/dev/null
img web-app-nginx-base web-app baseline $HOME/fe/base/frontend/client-app
img web-app-nginx-base web-app after $HOME/fe/web/frontend/client-app
img admin-dashboard-nginx-base admin-dashboard baseline $HOME/fe/base/frontend/admin-dashboard
img admin-dashboard-nginx-base admin-dashboard after $HOME/fe/admin/frontend/admin-dashboard
fs() { # fix tag lockfile
  local fix=$1 tag=$2 lf=$3 d=$E/$1; mkdir -p $d
  hdr "$fix: trivy fs $lf ($tag)"
  $T fs $OPTS --format json --output /tmp/$fix-$tag.json $lf
  compact /tmp/$fix-$tag.json > $d/trivy-fs-$tag.json
  $T fs $OPTS --format table $lf > $d/trivy-fs-$tag.txt
  echo "$tag $lf $(counts /tmp/$fix-$tag.json)" | tee -a $d/summary.txt
}
fs web-app-npm-deps baseline $HOME/fe/base/frontend/client-app/package-lock.json
fs web-app-npm-deps after $HOME/fe/npm/frontend/client-app/package-lock.json
img web-app-npm-deps web-app npm-after $HOME/fe/npm/frontend/client-app
fs admin-dashboard-nginx-base app-lockfile-residual $HOME/fe/base/frontend/admin-dashboard/package-lock.json
hdr "Residual app-package findings (admin-dashboard lockfile, unchanged)"; jq -r '.Results[]?.Vulnerabilities[]?|"\(.PkgName) \(.InstalledVersion) \(.VulnerabilityID) \(.Severity) fixed=\(.FixedVersion)"' /tmp/admin-dashboard-nginx-base-app-lockfile-residual.json | sort | uniq | head -30
hdr "SUMMARY"; for f in $E/*/summary.txt; do echo "-- ${f%/summary.txt}"; cat $f; done
