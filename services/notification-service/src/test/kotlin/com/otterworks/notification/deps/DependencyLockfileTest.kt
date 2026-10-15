package com.otterworks.notification.deps

import java.io.File
import kotlin.test.Test
import kotlin.test.assertTrue

/**
 * Guards the committed Gradle lock state (gradle.lockfile) so transitive dependency
 * resolution stays pinned across machines and CI. Gradle runs tests with the module
 * directory as the working directory, which is where the lockfile lives.
 */
class DependencyLockfileTest {

    private val lockfile = File("gradle.lockfile")

    @Test
    fun lockfileIsCommittedNextToTheBuildScript() {
        assertTrue(File("build.gradle.kts").isFile, "test must run from the module directory")
        assertTrue(lockfile.isFile, "gradle.lockfile is missing; run ./gradlew dependencies --write-locks")
    }

    @Test
    fun lockfilePinsEveryShippedConfiguration() {
        val lockedConfigurations = lockfile.readLines()
            .filter { it.isNotBlank() && !it.startsWith("#") && !it.startsWith("empty=") }
            .flatMap { it.substringAfter('=').split(',') }
            .toSet()

        listOf("compileClasspath", "runtimeClasspath", "testCompileClasspath", "testRuntimeClasspath")
            .forEach { configuration ->
                assertTrue(configuration in lockedConfigurations, "no locked dependencies for $configuration")
            }
    }
}
