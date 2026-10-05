package com.otterworks.legacyportal.lambda.announcements;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.amazonaws.services.lambda.runtime.events.APIGatewayV2HTTPEvent;
import com.amazonaws.services.lambda.runtime.events.APIGatewayV2HTTPResponse;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.junit.jupiter.api.Test;

class HandlerTest {
    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Test
    void healthIncludesInterpolatedPortalBanner() throws Exception {
        APIGatewayV2HTTPResponse response = handler(new FakeRepository())
                .handleRequest(event("GET", "/health", null, null), null);

        assertEquals(200, response.getStatusCode());
        assertEquals("application/json", response.getHeaders().get("Content-Type"));
        JsonNode body = MAPPER.readTree(response.getBody());
        assertEquals("UP", body.get("status").asText());
        assertEquals("legacy-portal", body.get("service").asText());
        assertEquals(
                "OtterWorks Portal (on-prem) - contact portal-support@otterworks.example",
                body.get("banner").asText());
    }

    @Test
    void actuatorHealthIncludesProbeGroups() throws Exception {
        APIGatewayV2HTTPResponse response = handler(new FakeRepository())
                .handleRequest(event("GET", "/actuator/health", null, null), null);

        assertEquals(200, response.getStatusCode());
        assertEquals("{\"status\":\"UP\",\"groups\":[\"liveness\",\"readiness\"]}", response.getBody());
    }

    @Test
    void publishedOnlyDefaultsTrueAndCanListAll() throws Exception {
        FakeRepository repository = new FakeRepository();
        repository.insert(new Announcement(null, "published", "visible", true, Instant.parse("2024-01-01T00:00:00Z")));
        repository.insert(new Announcement(null, "draft", "hidden", false, Instant.parse("2024-01-02T00:00:00Z")));
        Handler handler = handler(repository);

        JsonNode published = MAPPER.readTree(handler.handleRequest(event("GET", "/api/announcements", null, null), null)
                .getBody());
        APIGatewayV2HTTPEvent allEvent = event("GET", "/api/announcements", null, null);
        allEvent.setQueryStringParameters(Map.of("publishedOnly", "no"));
        JsonNode all = MAPPER.readTree(handler.handleRequest(allEvent, null).getBody());

        assertEquals(1, published.size());
        assertEquals("published", published.get(0).get("title").asText());
        assertEquals(2, all.size());
    }

    @Test
    void invalidPublishedOnlyUsesSpringBooleanConversionMessage() throws Exception {
        APIGatewayV2HTTPEvent request = event("GET", "/api/announcements", null, Map.of("publishedOnly", "abc"));

        APIGatewayV2HTTPResponse response = handler(new FakeRepository()).handleRequest(request, null);

        assertEquals(400, response.getStatusCode());
        assertEquals("{\"error\":\"Bad Request\",\"message\":\"Invalid boolean value [abc]\"}", response.getBody());
    }

    @Test
    void createReturnsOrderedJsonWithUtcInstantAndCreatedStatus() throws Exception {
        String request = "{\"title\":\"Notice\",\"body\":\"Hello\",\"published\":true}";
        APIGatewayV2HTTPEvent requestEvent = event(
                "POST", "/api/announcements", request, null, Map.of("Content-Type", "application/json"));
        requestEvent.setIsBase64Encoded(true);
        requestEvent.setBody(
                java.util.Base64.getEncoder().encodeToString(request.getBytes(StandardCharsets.UTF_8)));
        APIGatewayV2HTTPResponse response = handler(new FakeRepository()).handleRequest(requestEvent, null);

        assertEquals(201, response.getStatusCode());
        int createdAtField = response.getBody().indexOf("\"createdAt\":");
        assertEquals(
                "{\"id\":1,\"title\":\"Notice\",\"body\":\"Hello\",\"published\":true,\"createdAt\":",
                response.getBody().substring(0, createdAtField + 12));
        JsonNode body = MAPPER.readTree(response.getBody());
        assertEquals(1L, body.get("id").asLong());
        assertEquals("202", body.get("createdAt").asText().substring(0, 3));
        assertTrue(body.get("createdAt").asText().endsWith("Z"));
    }

    @Test
    void createCoercesJacksonScalarValuesAndIgnoresUnknownFieldsAndTrailingTokens() throws Exception {
        Handler handler = handler(new FakeRepository());
        APIGatewayV2HTTPResponse scalarValues = handler.handleRequest(
                event(
                        "POST",
                        "/api/announcements",
                        "{\"title\":123,\"body\":true,\"published\":\"TRUE\",\"author\":\"otter\"}",
                        null,
                        Map.of("content-type", "application/json")),
                null);
        APIGatewayV2HTTPResponse trailingTokens = handler.handleRequest(
                event(
                        "POST",
                        "/api/announcements",
                        "{\"title\":\"Trailing\",\"body\":\"tokens\"} xyz",
                        null,
                        Map.of("Content-Type", "application/json")),
                null);
        APIGatewayV2HTTPResponse stringFalse = handler.handleRequest(
                event(
                        "POST",
                        "/api/announcements",
                        "{\"title\":\"False\",\"body\":\"string\",\"published\":\"fAlSe\"}",
                        null,
                        Map.of("Content-Type", "application/json")),
                null);
        APIGatewayV2HTTPResponse integerTrue = handler.handleRequest(
                event(
                        "POST",
                        "/api/announcements",
                        "{\"title\":\"Integer\",\"body\":\"one\",\"published\":1}",
                        null,
                        Map.of("Content-Type", "application/json")),
                null);
        APIGatewayV2HTTPResponse integerFalse = handler.handleRequest(
                event(
                        "POST",
                        "/api/announcements",
                        "{\"title\":\"Integer\",\"body\":\"zero\",\"published\":0}",
                        null,
                        Map.of("Content-Type", "application/json")),
                null);

        assertEquals(201, scalarValues.getStatusCode());
        JsonNode coerced = MAPPER.readTree(scalarValues.getBody());
        assertEquals("123", coerced.get("title").asText());
        assertEquals("true", coerced.get("body").asText());
        assertTrue(coerced.get("published").asBoolean());
        assertEquals(201, trailingTokens.getStatusCode());
        assertEquals("Trailing", MAPPER.readTree(trailingTokens.getBody()).get("title").asText());
        assertFalse(MAPPER.readTree(stringFalse.getBody()).get("published").asBoolean());
        assertTrue(MAPPER.readTree(integerTrue.getBody()).get("published").asBoolean());
        assertFalse(MAPPER.readTree(integerFalse.getBody()).get("published").asBoolean());
    }

    @Test
    void createAcceptsLatin1EncodedAndAlreadyDecodedBodies() throws Exception {
        String body = "{\"title\":\"café\",\"body\":\"latin-1 body\",\"published\":true}";
        Map<String, String> headers = Map.of("Content-Type", "application/json;charset=ISO-8859-1");
        APIGatewayV2HTTPEvent encodedEvent = event("POST", "/api/announcements", null, null, headers);
        encodedEvent.setIsBase64Encoded(true);
        encodedEvent.setBody(java.util.Base64.getEncoder()
                .encodeToString(body.getBytes(StandardCharsets.ISO_8859_1)));

        APIGatewayV2HTTPResponse encoded =
                handler(new FakeRepository()).handleRequest(encodedEvent, null);
        APIGatewayV2HTTPResponse decoded = handler(new FakeRepository())
                .handleRequest(event("POST", "/api/announcements", body, null, headers), null);

        assertEquals(201, encoded.getStatusCode());
        assertEquals("café", MAPPER.readTree(encoded.getBody()).get("title").asText());
        assertEquals(201, decoded.getStatusCode());
        assertEquals("café", MAPPER.readTree(decoded.getBody()).get("title").asText());
    }

    @Test
    void createRejectsInvalidJsonAndValidationFailuresWithDefaultError() throws Exception {
        Handler handler = handler(new FakeRepository());
        List<String> invalidBodies = List.of(
                "{\"body\":\"no title\"}",
                "{\"title\":null,\"body\":\"body\"}",
                "{\"title\":\"title\"}",
                "{\"title\":\"title\",\"body\":null}",
                "{\"title\":\"   \",\"body\":\"body\"}",
                "{\"title\":\"title\",\"body\":\"  \"}",
                "{\"title\":\"" + "x".repeat(201) + "\",\"body\":\"body\"}",
                "{\"title\":\"title\",\"body\":\"" + "y".repeat(4001) + "\"}",
                "{\"title\":",
                "",
                "[]",
                "{\"title\":{},\"body\":\"body\"}",
                "{\"title\":\"title\",\"body\":\"body\",\"published\":{}}",
                "{\"Title\":\"Case\",\"body\":\"body\"}");

        for (String body : invalidBodies) {
            APIGatewayV2HTTPResponse response = handler.handleRequest(
                    event("POST", "/api/announcements", body, null, Map.of("Content-Type", "application/json")),
                    null);

            assertEquals(400, response.getStatusCode(), body);
            assertDefaultError(response, 400, "Bad Request", "/api/announcements");
        }
    }

    @Test
    void unsupportedOrMissingContentTypeUsesDefault415BeforeBodyParsing() throws Exception {
        Handler handler = handler(new FakeRepository());
        APIGatewayV2HTTPResponse unsupported = handler.handleRequest(
                event("POST", "/api/announcements", "not json", null, Map.of("Content-Type", "text/plain")), null);
        APIGatewayV2HTTPResponse missing = handler.handleRequest(
                event("POST", "/api/announcements", "{\"title\":\"x\",\"body\":\"y\"}", null), null);

        assertDefaultError(unsupported, 415, "Unsupported Media Type", "/api/announcements");
        assertDefaultError(missing, 415, "Unsupported Media Type", "/api/announcements");
    }

    @Test
    void jsonSuffixMediaTypeIsAccepted() throws Exception {
        APIGatewayV2HTTPResponse response = handler(new FakeRepository()).handleRequest(
                event(
                        "POST",
                        "/api/announcements",
                        "{\"title\":\"Notice\",\"body\":\"JSON suffix\"}",
                        null,
                        Map.of("Content-Type", "application/vnd.otterworks+json; charset=UTF-8")),
                null);

        assertEquals(201, response.getStatusCode());
    }

    @Test
    void wrongMethodsUseDefault405AndUnknownSubpathsUseDefault404() throws Exception {
        Handler handler = handler(new FakeRepository());
        List<APIGatewayV2HTTPEvent> wrongMethods = List.of(
                event("DELETE", "/api/announcements/1", null, null),
                event("PUT", "/api/announcements", "{\"title\":\"x\",\"body\":\"y\"}", null),
                event("GET", "/api/announcements/1/publish", null, null),
                event("POST", "/api/announcements/1", null, null));

        for (APIGatewayV2HTTPEvent request : wrongMethods) {
            APIGatewayV2HTTPResponse response = handler.handleRequest(request, null);
            assertEquals(405, response.getStatusCode());
            assertDefaultError(response, 405, "Method Not Allowed", request.getRawPath());
        }

        APIGatewayV2HTTPResponse unknown = handler.handleRequest(
                event("GET", "/api/announcements/1/other/", null, null), null);
        assertEquals(404, unknown.getStatusCode());
        assertDefaultNotFound(unknown, "/api/announcements/1/other/");
    }

    @Test
    void trailingSlashMatchesCollectionForGetAndCreate() throws Exception {
        Handler handler = handler(new FakeRepository());

        APIGatewayV2HTTPResponse get = handler.handleRequest(event("GET", "/api/announcements/", null, null), null);
        APIGatewayV2HTTPResponse post = handler.handleRequest(
                event(
                        "POST",
                        "/api/announcements/",
                        "{\"title\":\"Trailing slash\",\"body\":\"created\"}",
                        null,
                        Map.of("Content-Type", "application/json")),
                null);

        assertEquals(200, get.getStatusCode());
        assertEquals(201, post.getStatusCode());
    }

    @Test
    void unacceptableAcceptReturnsEmpty406WithoutContentType() throws Exception {
        Handler handler = handler(new FakeRepository());
        APIGatewayV2HTTPResponse unacceptable = handler.handleRequest(
                event("GET", "/health", null, null, Map.of("Accept", "application/xml")), null);
        APIGatewayV2HTTPResponse browser = handler.handleRequest(
                event(
                        "GET",
                        "/health",
                        null,
                        null,
                        Map.of("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")),
                null);

        assertEquals(406, unacceptable.getStatusCode());
        assertEquals("", unacceptable.getBody());
        assertTrue(unacceptable.getHeaders() == null || !unacceptable.getHeaders().containsKey("Content-Type"));
        assertEquals(200, browser.getStatusCode());
        assertEquals("application/json", browser.getHeaders().get("Content-Type"));
    }

    @Test
    void unknownAndMissingAnnouncementUseNotFoundErrorShape() throws Exception {
        Handler handler = handler(new FakeRepository());

        APIGatewayV2HTTPResponse unknown = handler.handleRequest(event("GET", "/not-a-route", null, null), null);
        APIGatewayV2HTTPResponse missing =
                handler.handleRequest(event("GET", "/api/announcements/42", null, null), null);

        assertEquals(404, unknown.getStatusCode());
        assertDefaultNotFound(unknown, "/not-a-route");
        assertEquals(404, missing.getStatusCode());
        assertEquals("announcement 42 not found", MAPPER.readTree(missing.getBody()).get("message").asText());
    }

    @Test
    void caseMismatchedAndUnknownPathsUseDefaultErrorWithRawPath() throws Exception {
        Handler handler = handler(new FakeRepository());
        List<String> paths = List.of(
                "/HEALTH",
                "/Actuator/health",
                "/API/announcements",
                "/API/preferences/alice",
                "/api/Feedback?userId=alice",
                "/does-not-exist");

        for (String path : paths) {
            APIGatewayV2HTTPResponse response =
                    handler.handleRequest(event("GET", path, null, null), null);
            String expectedPath = path.contains("?") ? path.substring(0, path.indexOf('?')) : path;

            assertEquals(404, response.getStatusCode(), path);
            assertEquals("application/json", response.getHeaders().get("Content-Type"), path);
            assertDefaultNotFound(response, expectedPath);
        }
    }

    @Test
    void invalidAndOverflowingIdsUseLongParseNumberFormatMessage() throws Exception {
        Handler handler = handler(new FakeRepository());

        for (String id : List.of("abc", "99999999999999999999")) {
            APIGatewayV2HTTPResponse response =
                    handler.handleRequest(event("GET", "/api/announcements/" + id, null, null), null);

            assertEquals(400, response.getStatusCode());
            assertEquals(
                    "{\"error\":\"Bad Request\",\"message\":\"For input string: \\\"" + id + "\\\"\"}",
                    response.getBody());
        }
    }

    @Test
    void createValidatesNotBlankAndSize() throws Exception {
        Handler handler = handler(new FakeRepository());

        APIGatewayV2HTTPResponse blank = handler.handleRequest(
                event(
                        "POST",
                        "/api/announcements",
                        "{\"title\":\"  \",\"body\":\"body\"}",
                        null,
                        Map.of("Content-Type", "application/json")),
                null);
        APIGatewayV2HTTPResponse tooLong = handler.handleRequest(
                event("POST", "/api/announcements", "{\"title\":\""
                        + "x".repeat(201) + "\",\"body\":\"body\"}", null, Map.of("Content-Type", "application/json")),
                null);

        assertEquals(400, blank.getStatusCode());
        assertEquals(400, tooLong.getStatusCode());
        assertDefaultError(blank, 400, "Bad Request", "/api/announcements");
        assertDefaultError(tooLong, 400, "Bad Request", "/api/announcements");
    }

    private static Handler handler(FakeRepository repository) {
        return new Handler(repository);
    }

    private static void assertDefaultNotFound(APIGatewayV2HTTPResponse response, String path) throws Exception {
        assertDefaultError(response, 404, "Not Found", path);
    }

    private static void assertDefaultError(
            APIGatewayV2HTTPResponse response, int status, String reason, String path) throws Exception {
        JsonNode body = MAPPER.readTree(response.getBody());
        String timestamp = body.get("timestamp").asText();
        assertTrue(timestamp.matches("\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}\\.\\d{3}\\+00:00"));
        assertEquals(
                "{\"timestamp\":\"" + timestamp + "\",\"status\":" + status + ",\"error\":\"" + reason
                        + "\",\"path\":\"" + path + "\"}",
                response.getBody());
        assertEquals(status, response.getStatusCode());
        assertEquals("application/json", response.getHeaders().get("Content-Type"));
    }

    private static APIGatewayV2HTTPEvent event(String method, String path, String body, Map<String, String> query) {
        return event(method, path, body, query, null);
    }

    private static APIGatewayV2HTTPEvent event(
            String method, String path, String body, Map<String, String> query, Map<String, String> headers) {
        return APIGatewayV2HTTPEvent.builder()
                .withRawPath(path)
                .withRequestContext(APIGatewayV2HTTPEvent.RequestContext.builder()
                        .withHttp(APIGatewayV2HTTPEvent.RequestContext.Http.builder()
                                .withMethod(method)
                                .withPath(path)
                                .build())
                        .build())
                .withQueryStringParameters(query)
                .withHeaders(headers)
                .withBody(body)
                .withIsBase64Encoded(false)
                .build();
    }

    private static final class FakeRepository implements AnnouncementRepository {
        private final Map<Long, Announcement> announcements = new LinkedHashMap<>();
        private long nextId = 1;

        @Override
        public Announcement save(Announcement announcement) {
            announcements.put(announcement.getId(), announcement);
            return announcement;
        }

        @Override
        public Announcement insert(Announcement announcement) {
            Announcement created = new Announcement(
                    nextId++,
                    announcement.getTitle(),
                    announcement.getBody(),
                    announcement.isPublished(),
                    announcement.getCreatedAt());
            announcements.put(created.getId(), created);
            return created;
        }

        @Override
        public Optional<Announcement> findById(Long id) {
            return Optional.ofNullable(announcements.get(id));
        }

        @Override
        public List<Announcement> findAll() {
            return new ArrayList<>(announcements.values());
        }

        @Override
        public List<Announcement> findByPublishedTrueOrderByCreatedAtDesc() {
            return announcements.values().stream()
                    .filter(Announcement::isPublished)
                    .sorted(Comparator.comparing(Announcement::getCreatedAt).reversed())
                    .toList();
        }

        @Override
        public Announcement updatePublished(Long id, boolean published) {
            Announcement existing = announcements.get(id);
            Announcement updated = new Announcement(
                    id, existing.getTitle(), existing.getBody(), published, existing.getCreatedAt());
            announcements.put(id, updated);
            return updated;
        }
    }
}
