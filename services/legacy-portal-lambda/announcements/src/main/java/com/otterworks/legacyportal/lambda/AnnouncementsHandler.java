package com.otterworks.legacyportal.lambda;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.Map;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestStreamHandler;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.otterworks.legacyportal.lambda.announcements.AnnouncementService;
import com.otterworks.legacyportal.lambda.announcements.DataApiAnnouncementRepository;
import com.otterworks.legacyportal.lambda.announcements.EventBridgeAnnouncementEvents;
import com.otterworks.legacyportal.lambda.common.PortalBrandingSettings;
import com.otterworks.legacyportal.lambda.http.Dispatcher;

import software.amazon.awssdk.services.rdsdata.RdsDataClient;

/**
 * Lambda entry point for the announcements bounded context plus the shared
 * {@code /health} and {@code /actuator/*} plumbing of the legacy portal monolith.
 * Parses the API Gateway HTTP API (payload format 2.0) proxy event and answers with
 * the proxy response shape.
 */
public class AnnouncementsHandler implements RequestStreamHandler {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private final Dispatcher dispatcher;
    private final boolean failReads;

    public AnnouncementsHandler() {
        this(defaultDispatcher(), "1".equals(System.getenv("FAIL_READS")));
    }

    AnnouncementsHandler(Dispatcher dispatcher, boolean failReads) {
        this.dispatcher = dispatcher;
        this.failReads = failReads;
    }

    private static Dispatcher defaultDispatcher() {
        RdsDataClient client = RdsDataClient.builder().build();
        DataApiAnnouncementRepository repository = new DataApiAnnouncementRepository(
                client,
                System.getenv("CLUSTER_ARN"),
                System.getenv("SECRET_ARN"),
                System.getenv("DB_NAME"),
                System.getenv("DB_SCHEMA"));
        return new Dispatcher(new AnnouncementService(repository, EventBridgeAnnouncementEvents.fromEnvironment()),
                new PortalBrandingSettings());
    }

    @Override
    public void handleRequest(InputStream input, OutputStream output, Context context) throws IOException {
        JsonNode event = MAPPER.readTree(input);

        String method = event.path("requestContext").path("http").path("method").asText("");
        String path = event.path("rawPath").asText("/");
        String rawQuery = event.path("rawQueryString").isTextual()
                ? event.path("rawQueryString").asText() : "";

        Map<String, String> headers = new LinkedHashMap<>();
        JsonNode headersNode = event.path("headers");
        if (headersNode.isObject()) {
            headersNode.fields().forEachRemaining(
                    e -> headers.put(e.getKey().toLowerCase(java.util.Locale.ROOT), e.getValue().asText()));
        }

        byte[] body = new byte[0];
        JsonNode bodyNode = event.path("body");
        if (bodyNode.isTextual()) {
            if (event.path("isBase64Encoded").asBoolean(false)) {
                body = Base64.getDecoder().decode(bodyNode.asText());
            } else {
                body = bodyNode.asText().getBytes(StandardCharsets.UTF_8);
            }
        }

        // FAIL_READS=1 is the canary demo's bad build: the same code, with every GET answering 500.
        Dispatcher.Response response = failReads && "GET".equalsIgnoreCase(method)
                ? dispatcher.failedRead(path)
                : dispatcher.dispatch(new Dispatcher.Request(method, path, rawQuery, headers, body));

        ObjectNode out = MAPPER.createObjectNode();
        out.put("statusCode", response.status());
        ObjectNode outHeaders = out.putObject("headers");
        for (Map.Entry<String, String> e : response.headers().entrySet()) {
            outHeaders.put(e.getKey(), e.getValue());
        }
        out.put("body", response.body() == null ? "" : response.body());
        out.put("isBase64Encoded", false);
        output.write(MAPPER.writeValueAsBytes(out));
    }
}
