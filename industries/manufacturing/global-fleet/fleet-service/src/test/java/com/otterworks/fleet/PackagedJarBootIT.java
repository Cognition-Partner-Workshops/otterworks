package com.otterworks.fleet;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.dataformat.yaml.YAMLFactory;
import io.zonky.test.db.postgres.embedded.EmbeddedPostgres;
import java.io.IOException;
import java.net.ServerSocket;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.List;
import java.util.concurrent.TimeUnit;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.fail;

class PackagedJarBootIT {

    private static final Duration STARTUP_TIMEOUT = Duration.ofSeconds(120);

    @Test
    void packagedJarServesApiDocsAndProfile() throws Exception {
        String profile = System.getProperty("spring.profiles.active");
        if (profile == null || profile.isBlank()) {
            throw new AssertionError("spring.profiles.active must be set by the Maven profile");
        }

        Path jar = findPackagedJar();
        Path log = Path.of("target", "boot-" + profile + ".log");
        Files.createDirectories(log.getParent());

        EmbeddedPostgres postgres = EmbeddedPostgres.builder().start();
        Process process = null;
        try {
            int port = freePort();
            Path java = Path.of(System.getProperty("java.home"), "bin", "java");
            ProcessBuilder processBuilder = new ProcessBuilder(
                    java.toString(),
                    "-jar",
                    jar.toAbsolutePath().toString(),
                    "--server.port=" + port);
            processBuilder.environment().put("SPRING_PROFILES_ACTIVE", profile);
            processBuilder.environment().put("DB_URL", postgres.getJdbcUrl("postgres", "postgres"));
            processBuilder.environment().put("DB_USER", "postgres");
            processBuilder.environment().put("DB_PASSWORD", "postgres");
            processBuilder.redirectErrorStream(true);
            processBuilder.redirectOutput(log.toFile());
            process = processBuilder.start();

            HttpClient client = HttpClient.newBuilder()
                    .connectTimeout(Duration.ofSeconds(1))
                    .build();
            String baseUrl = "http://localhost:" + port;
            awaitProfileEndpoint(client, baseUrl, process, log);

            HttpResponse<String> apiDocs = get(client, baseUrl + "/v3/api-docs", log);
            assertStatus(apiDocs, 200, "/v3/api-docs", log);
            if (!apiDocs.body().contains("/api/v1/profile")) {
                fail(withLogTail("OpenAPI document does not contain /api/v1/profile", log));
            }

            HttpResponse<String> profileResponse = get(client, baseUrl + "/api/v1/profile", log);
            assertStatus(profileResponse, 200, "/api/v1/profile", log);
            String expectedCurrency = expectedCurrency(profile, log);
            String actualCurrency = new ObjectMapper().readTree(profileResponse.body())
                    .path("currency")
                    .asText();
            if (!expectedCurrency.equals(actualCurrency)) {
                fail(withLogTail(
                        "Expected profile currency " + expectedCurrency + " but received " + actualCurrency,
                        log));
            }
        } finally {
            stopProcess(process);
            postgres.close();
        }
    }

    private static Path findPackagedJar() throws IOException {
        try (Stream<Path> files = Files.list(Path.of("target"))) {
            List<Path> jars = files
                    .filter(path -> path.getFileName().toString().startsWith("fleet-service-"))
                    .filter(path -> path.getFileName().toString().endsWith(".jar"))
                    .filter(path -> !path.getFileName().toString().endsWith(".jar.original"))
                    .toList();
            if (jars.size() != 1) {
                throw new AssertionError(
                        "Expected exactly one packaged target/fleet-service-*.jar, found " + jars.size());
            }
            return jars.get(0);
        }
    }

    private static int freePort() throws IOException {
        try (ServerSocket socket = new ServerSocket(0)) {
            return socket.getLocalPort();
        }
    }

    private static void awaitProfileEndpoint(
            HttpClient client, String baseUrl, Process process, Path log) throws Exception {
        long deadline = System.nanoTime() + STARTUP_TIMEOUT.toNanos();
        HttpRequest request = HttpRequest.newBuilder(URI.create(baseUrl + "/api/v1/profile"))
                .timeout(Duration.ofSeconds(3))
                .GET()
                .build();
        while (System.nanoTime() < deadline) {
            if (!process.isAlive()) {
                throw new AssertionError(withLogTail(
                        "Packaged jar exited before /api/v1/profile answered; exit code "
                                + process.exitValue(),
                        log));
            }
            try {
                HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
                if (response.statusCode() == 200) {
                    return;
                }
            } catch (IOException ignored) {
                // The server is still starting.
            }
            Thread.sleep(500);
        }
        throw new AssertionError(withLogTail(
                "Timed out after " + STARTUP_TIMEOUT.toSeconds() + " seconds waiting for /api/v1/profile",
                log));
    }

    private static HttpResponse<String> get(HttpClient client, String url, Path log) {
        HttpRequest request = HttpRequest.newBuilder(URI.create(url))
                .timeout(Duration.ofSeconds(10))
                .GET()
                .build();
        try {
            return client.send(request, HttpResponse.BodyHandlers.ofString());
        } catch (IOException | InterruptedException exception) {
            if (exception instanceof InterruptedException) {
                Thread.currentThread().interrupt();
            }
            throw new AssertionError(withLogTail("Request failed for " + url, log), exception);
        }
    }

    private static void assertStatus(
            HttpResponse<String> response, int expectedStatus, String endpoint, Path log) {
        if (response.statusCode() != expectedStatus) {
            fail(withLogTail(
                    endpoint + " returned HTTP " + response.statusCode() + " instead of " + expectedStatus
                            + "; response body: " + response.body(),
                    log));
        }
    }

    private static String expectedCurrency(String profile, Path log) {
        Path profileConfig = Path.of("src", "main", "resources", "application-" + profile + ".yml");
        try {
            JsonNode config = new ObjectMapper(new YAMLFactory()).readTree(Files.readString(profileConfig));
            String currency = config.path("fleet").path("country").path("currency").asText();
            if (currency.isBlank()) {
                throw new AssertionError(withLogTail(
                        "Missing fleet.country.currency in " + profileConfig,
                        log));
            }
            return currency;
        } catch (IOException exception) {
            throw new AssertionError(withLogTail("Could not read " + profileConfig, log), exception);
        }
    }

    private static void stopProcess(Process process) throws InterruptedException {
        if (process == null || !process.isAlive()) {
            return;
        }
        process.destroy();
        if (!process.waitFor(15, TimeUnit.SECONDS)) {
            process.destroyForcibly();
            process.waitFor();
        }
    }

    private static String withLogTail(String message, Path log) {
        try {
            List<String> lines = Files.exists(log) ? Files.readAllLines(log) : List.of();
            int start = Math.max(0, lines.size() - 60);
            return message + System.lineSeparator() + "Last log lines:" + System.lineSeparator()
                    + String.join(System.lineSeparator(), lines.subList(start, lines.size()));
        } catch (IOException exception) {
            return message + System.lineSeparator() + "Could not read boot log " + log + ": " + exception;
        }
    }
}
