package com.otterworks.auth.supplychain;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
import org.junit.jupiter.api.Test;

/**
 * Guards the Gradle dependency lock state (SonarCloud text:S8569). Without a committed
 * gradle.lockfile, transitive dependency resolution is re-run on every fresh build and may silently
 * pick up a newly published (possibly malicious) version.
 */
class DependencyLockfileTest {

  private static final Path LOCKFILE = Paths.get("gradle.lockfile");

  @Test
  void lockfile_shouldBeCommittedNextToBuildGradle() {
    assertThat(LOCKFILE).exists().isRegularFile();
  }

  @Test
  void lockfile_shouldPinRuntimeAndCompileClasspaths() throws IOException {
    List<String> lockedEntries =
        Files.readAllLines(LOCKFILE).stream().filter(line -> !line.startsWith("#")).toList();

    assertThat(lockedEntries).isNotEmpty();
    assertThat(lockedEntries)
        .anyMatch(line -> line.contains("=") && line.contains("runtimeClasspath"));
    assertThat(lockedEntries)
        .anyMatch(line -> line.contains("=") && line.contains("compileClasspath"));
    assertThat(lockedEntries)
        .filteredOn(line -> !line.startsWith("empty="))
        .allMatch(line -> line.matches("[^:=]+:[^:=]+:[^=]+=.+"));
  }
}
