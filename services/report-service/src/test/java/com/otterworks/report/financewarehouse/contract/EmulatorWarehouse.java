package com.otterworks.report.financewarehouse.contract;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.concurrent.TimeUnit;

class EmulatorWarehouse implements ContractWarehouse {
    private final String target;

    EmulatorWarehouse(String target) {
        this.target = target;
    }

    @Override
    public JsonNode execute(String sql, int period) throws Exception {
        String query = ReplayWarehouse.queryName(sql);
        String python = System.getenv().getOrDefault("CONTRACT_KIT_PYTHON", "python3");
        String bridge = System.getenv().getOrDefault("CONTRACT_KIT_BRIDGE", "../../consumers/contract-kit/bridge.py");
        List<String> command = new ArrayList<>(Arrays.asList(python, bridge,
                "--target", target, "--query", query));
        if ("true".equals(System.getenv("CONTRACT_RECORD"))) {
            command.addAll(Arrays.asList("--record", "contract/recorded/teradata/" + query + ".json"));
        }
        File output = File.createTempFile("finance-contract-", ".json");
        File error = File.createTempFile("finance-contract-", ".log");
        Process process = null;
        try {
            process = new ProcessBuilder(command).redirectOutput(output).redirectError(error).start();
            try (java.io.OutputStream input = process.getOutputStream()) {
                input.write(sql.replace("?", Integer.toString(period)).getBytes(StandardCharsets.UTF_8));
            }
            if (!process.waitFor(60, TimeUnit.SECONDS)) {
                throw new IllegalStateException("Contract bridge timed out");
            }
            if (process.exitValue() != 0) {
                throw new IllegalStateException(new String(Files.readAllBytes(error.toPath()), StandardCharsets.UTF_8));
            }
            return new ObjectMapper().readTree(output);
        } finally {
            if (process != null && process.isAlive()) {
                process.destroyForcibly();
            }
            Files.deleteIfExists(output.toPath());
            Files.deleteIfExists(error.toPath());
        }
    }
}
