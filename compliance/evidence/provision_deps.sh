#!/usr/bin/env bash
# Source this file so the harness inherits the selected toolchains.
set -euo pipefail

provision_deps() {
  local version home package candidate arch
  local -a apt=(sudo -n apt-get)
  local -a elevate=(sudo -n)
  if [[ $EUID == 0 ]]; then apt=(apt-get); elevate=(); fi
  "${apt[@]}" update
  "${apt[@]}" install -y --no-install-recommends ca-certificates curl unzip maven
  arch="$(dpkg --print-architecture)"
  for version in 11 21; do
    local variable="JAVA_HOME_${version}_X64"
    home="${!variable:-}"
    if [[ -z "$home" || ! -x "$home/bin/javac" ]]; then
      home=""
      for candidate in /usr/lib/jvm/java-"$version"-openjdk-* /usr/lib/jvm/temurin-"$version"-jdk-*; do
        if [[ -x "$candidate/bin/javac" ]]; then home="$candidate"; break; fi
      done
    fi
    if [[ -z "$home" ]]; then
      package="openjdk-$version-jdk"
      if ! apt-cache show "$package" >/dev/null 2>&1; then
        "${apt[@]}" install -y --no-install-recommends gnupg
        mkdir -p "$HOME/.cache"
        curl -fsSL https://packages.adoptium.net/artifactory/api/gpg/key/public \
          | gpg --dearmor --yes -o "$HOME/.cache/adoptium.gpg"
        "${elevate[@]}" install -m 644 "$HOME/.cache/adoptium.gpg" /usr/share/keyrings/adoptium.gpg
        . /etc/os-release
        printf 'deb [signed-by=/usr/share/keyrings/adoptium.gpg] https://packages.adoptium.net/artifactory/deb %s main\n' "$VERSION_CODENAME" \
          | "${elevate[@]}" tee /etc/apt/sources.list.d/adoptium.list >/dev/null
        "${apt[@]}" update
        package="temurin-$version-jdk"
      fi
      "${apt[@]}" install -y --no-install-recommends "$package"
      if [[ $package == openjdk-* ]]; then
        home="/usr/lib/jvm/java-$version-openjdk-$arch"
      else
        home="/usr/lib/jvm/temurin-$version-jdk-$arch"
      fi
    fi
    "$home/bin/javac" -version
    export "$variable=$home"
  done
  local gradle="$HOME/opt/gradle-8.6"
  if [[ ! -x "$gradle/bin/gradle" ]]; then
    mkdir -p "$HOME/opt"
    curl -fL --retry 3 https://downloads.gradle.org/distributions/gradle-8.6-bin.zip -o "$HOME/opt/gradle-8.6-bin.zip"
    curl -fsSL https://downloads.gradle.org/distributions/gradle-8.6-bin.zip.sha256 -o "$HOME/opt/gradle-8.6-bin.zip.sha256"
    (cd "$HOME/opt" && printf '%s  gradle-8.6-bin.zip\n' "$(<gradle-8.6-bin.zip.sha256)" | sha256sum -c -)
    unzip -q -o "$HOME/opt/gradle-8.6-bin.zip" -d "$HOME/opt"
  fi
  export PATH="$gradle/bin:$PATH"
  if ! command -v uv >/dev/null; then python3 -m pip install --user uv==0.13.8; fi
}

provision_deps
