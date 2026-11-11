#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
cache="etl/spark/.cache/${NS:-sfx-d1110-before}"
mkdir -p "$cache/jars"
image=mirror.gcr.io/library/spark:3.5.3-scala2.12-java17-python3-ubuntu
version=$(docker run --rm --pull=never --label otterworks.run-token=sfx-d1110 --entrypoint bash "$image" -c 'basename /opt/spark/jars/scala-library-*.jar' | sed 's/scala-library-//;s/.jar//')
test "$version" = 2.12.18
base=https://maven-central.storage-download.googleapis.com/maven2
for artifact in "org/postgresql/postgresql/42.7.4/postgresql-42.7.4.jar" "org/scala-lang/scala-compiler/$version/scala-compiler-$version.jar"; do
    target="$cache/jars/${artifact##*/}"
    if [ ! -s "$target" ]; then
        curl --fail --location --retry 3 "$base/$artifact" -o "$target.tmp"
        mv "$target.tmp" "$target"
    fi
done
