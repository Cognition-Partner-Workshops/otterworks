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
        if (!Arrays.asList("teradata-emulator", "snowflake-semantics").contains(target)) {
            throw new IllegalArgumentException("Unsupported bridge target");
        }
        this.target = target;
    }

    static List<String> command(String python, String bridge, String target, String query, boolean record) {
        if (!python.matches("[A-Za-z0-9_./ -]+")
                || !new File(python).getName().matches("python(?:[0-9]+(?:\\.[0-9]+)*)?")) {
            throw new IllegalArgumentException("Invalid Python executable path");
        }
        if (python.contains("/") && !(new File(python).isFile() && new File(python).canExecute())) {
            throw new IllegalArgumentException("Python path must name an executable file");
        }
        if (!bridge.matches("[A-Za-z0-9_./ -]+") || !bridge.endsWith(".py") || !new File(bridge).isFile()) {
            throw new IllegalArgumentException("Invalid contract bridge path");
        }
        if (!Arrays.asList("teradata-emulator", "snowflake-semantics").contains(target)
                || !query.matches("[a-z][a-z0-9-]*")) {
            throw new IllegalArgumentException("Invalid contract target or query");
        }
        List<String> command = new ArrayList<>(Arrays.asList(python, bridge,
                "--target", target, "--query", query));
        if (record) {
            command.addAll(Arrays.asList("--record", "contract/recorded/teradata/" + query + ".json"));
        }
        return command;
    }

    @Override
    public JsonNode execute(String sql, int period) throws Exception {
        String query = ReplayWarehouse.queryName(sql);
        String python = System.getenv().getOrDefault("CONTRACT_KIT_PYTHON", "python3");
        String bridge = System.getenv().getOrDefault("CONTRACT_KIT_BRIDGE", "../../consumers/contract-kit/bridge.py");
        List<String> command = command(python, bridge, target, query, "true".equals(System.getenv("CONTRACT_RECORD")));
        File output = File.createTempFile("finance-contract-", ".json");
        File error = File.createTempFile("finance-contract-", ".log");
        Process process = null;
        try {
            ProcessBuilder builder = new ProcessBuilder().redirectOutput(output).redirectError(error);
            builder.command().addAll(command);
            builder.environment().put("TD_USER", "svc_exit_parity");
            process = builder.start();
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
