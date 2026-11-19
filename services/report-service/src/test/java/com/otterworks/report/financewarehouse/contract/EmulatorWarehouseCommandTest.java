package com.otterworks.report.financewarehouse.contract;

import org.junit.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.List;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.fail;

public class EmulatorWarehouseCommandTest {
    @Test
    public void preservesValidArgumentsAndRecording() throws Exception {
        Path bridge = Files.createTempFile("bridge with spaces", ".py");
        try {
            List<String> actual = EmulatorWarehouse.command("python3", bridge.toString(),
                    "teradata-emulator", "finance-reconciliation", true);
            assertEquals(Arrays.asList("python3", bridge.toString(), "--target", "teradata-emulator",
                    "--query", "finance-reconciliation", "--record",
                    "contract/recorded/teradata/finance-reconciliation.json"), actual);
            assertEquals(6, EmulatorWarehouse.command("python3", bridge.toString(),
                    "snowflake-semantics", "finance-reconciliation", false).size());
        } finally {
            Files.deleteIfExists(bridge);
        }
    }

    @Test
    public void rejectsShellMetacharactersAndEmptyPaths() throws Exception {
        Path directory = Files.createTempDirectory("contract-command-");
        Path bridge = Files.createFile(directory.resolve("bridge.py"));
        Path marker = directory.resolve("injected");
        try {
            for (String python : Arrays.asList("", "python3; touch " + marker, "python3 -c code", "/bin/sh")) {
                rejects(python, bridge.toString(), "teradata-emulator", "safe");
            }
            rejects("python3", "", "teradata-emulator", "safe");
            rejects("python3", bridge + ";touch " + marker, "teradata-emulator", "safe");
            rejects("python3", bridge.toString(), "teradata-emulator;touch " + marker, "safe");
            rejects("python3", bridge.toString(), "teradata-emulator", "../escape");
            rejects("python3", bridge.toString(), "teradata-emulator", "");
            assertFalse(Files.exists(marker));
        } finally {
            Files.deleteIfExists(bridge);
            Files.deleteIfExists(directory);
        }
    }

    private void rejects(String python, String bridge, String target, String query) {
        try {
            EmulatorWarehouse.command(python, bridge, target, query, false);
            fail("Unsafe command accepted");
        } catch (IllegalArgumentException expected) {
            // Rejected before creating a child process.
        }
    }
}
