#!/usr/bin/env bash
set -euo pipefail

sdk=${PEX_ANDROID_SDK:-${ANDROID_HOME:-${ANDROID_SDK_ROOT:-/opt/homebrew/share/android-commandlinetools}}}
fixtures=${PEX_ANDROID_FIXTURES:-"$(cd "$(dirname "$0")" && pwd)/out"}
java_home=${JAVA_HOME:-/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home}
export JAVA_HOME="$java_home"
export PATH="$java_home/bin:$PATH"
tools=$(find "$sdk/build-tools" -mindepth 1 -maxdepth 1 -type d | sort -V | tail -1)
android_jar="$sdk/platforms/android-34/android.jar"
source_dir=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$fixtures"
chmod 700 "$fixtures"

for required in "$tools/aapt2" "$tools/d8" "$tools/zipalign" "$tools/apksigner" "$android_jar" "$java_home/bin/javac" "$java_home/bin/keytool"; do
  test -x "$required" || test -r "$required" || { printf 'Missing Android fixture tool: %s\n' "$required" >&2; exit 1; }
done

key="$fixtures/test-key.p12"
if [[ ! -f "$key" ]]; then
  "$java_home/bin/keytool" -genkeypair -noprompt -storetype PKCS12 -keystore "$key" -storepass android -keypass android -alias pex-test -dname 'CN=PEX Fixture' -keyalg RSA -keysize 2048 -validity 10000
  chmod 600 "$key"
fi

for version in 1 2; do
  work="$fixtures/v$version-work"
  rm -rf "$work"
  mkdir -p "$work/classes" "$work/dex"
  sed "s|<manifest |<manifest android:versionCode=\"$version\" android:versionName=\"$version.0\" |" "$source_dir/AndroidManifest.xml" > "$work/AndroidManifest.xml"
  printf 'package dev.pex.crashapp; final class FixtureVersion { static final String NAME = "%s.0"; }\n' "$version" > "$work/FixtureVersion.java"
  "$tools/aapt2" link -I "$android_jar" --manifest "$work/AndroidManifest.xml" -o "$work/base.apk"
  "$java_home/bin/javac" -source 8 -target 8 -cp "$android_jar" -d "$work/classes" "$source_dir/src/dev/pex/crashapp/MainActivity.java" "$work/FixtureVersion.java"
  "$tools/d8" --lib "$android_jar" --min-api 23 --output "$work/dex" $(find "$work/classes" -type f -name '*.class' | sort)
  cp "$work/base.apk" "$work/unsigned.apk"
  (cd "$work/dex" && zip -X -q "$work/unsigned.apk" classes.dex)
  "$tools/zipalign" -f 4 "$work/unsigned.apk" "$work/aligned.apk"
  "$tools/apksigner" sign --ks "$key" --ks-pass pass:android --key-pass pass:android --out "$fixtures/crashapp-v$version.apk" "$work/aligned.apk"
  "$tools/apksigner" verify "$fixtures/crashapp-v$version.apk"
done

printf 'Built %s and %s\n' "$fixtures/crashapp-v1.apk" "$fixtures/crashapp-v2.apk"
