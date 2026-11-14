package com.otterworks.legacyportal.lambda.preferences;

import java.net.ServerSocket;
import java.net.Socket;
import java.net.URI;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.List;
import java.util.function.Supplier;
import software.amazon.awssdk.auth.credentials.AwsBasicCredentials;
import software.amazon.awssdk.auth.credentials.StaticCredentialsProvider;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.rdsdata.RdsDataClient;
import software.amazon.awssdk.services.rdsdata.model.ExecuteStatementRequest;
import software.amazon.awssdk.services.rdsdata.model.ExecuteStatementResponse;

final class DataApiTestSupport {
    private DataApiTestSupport() {
    }

    static final class FakeClock implements DataApiPreferenceRepository.RetryClock {
        long now;
        final List<Long> sleeps = new ArrayList<>();

        @Override
        public long nanoTime() {
            return now;
        }

        @Override
        public void sleep(long nanos) {
            sleeps.add(nanos);
            now += nanos;
        }
    }

    /** Answers each call from a script; the last step repeats. */
    static final class ScriptedClient implements RdsDataClient {
        final List<ExecuteStatementRequest> requests = new ArrayList<>();
        final Deque<Supplier<ExecuteStatementResponse>> steps = new ArrayDeque<>();

        ScriptedClient then(Supplier<ExecuteStatementResponse> step) {
            steps.add(step);
            return this;
        }

        @Override
        public ExecuteStatementResponse executeStatement(ExecuteStatementRequest request) {
            requests.add(request);
            return (steps.size() > 1 ? steps.poll() : steps.peek()).get();
        }

        @Override
        public String serviceName() {
            return "rds-data";
        }

        @Override
        public void close() {
        }
    }

    /** Accepts TCP connections and never answers, like a hung dependency. */
    static final class BlackHole implements AutoCloseable {
        private final ServerSocket server;
        private final List<Socket> held = new ArrayList<>();

        BlackHole() throws Exception {
            server = new ServerSocket(0);
            Thread acceptor = new Thread(() -> {
                try {
                    while (true) {
                        held.add(server.accept());
                    }
                } catch (Exception ignored) {
                    // closed
                }
            });
            acceptor.setDaemon(true);
            acceptor.start();
        }

        URI uri() {
            return URI.create("http://127.0.0.1:" + server.getLocalPort());
        }

        @Override
        public void close() throws Exception {
            server.close();
            for (Socket s : held) {
                s.close();
            }
        }
    }

    static RdsDataClient productionConfiguredClient(URI endpoint) {
        return RdsDataClient.builder()
                .region(Region.US_EAST_1)
                .credentialsProvider(StaticCredentialsProvider.create(
                        AwsBasicCredentials.create("AKIDEXAMPLE", "not-a-secret")))
                .endpointOverride(endpoint)
                .overrideConfiguration(DataApiPreferenceRepository.clientOverrides())
                .build();
    }
}
