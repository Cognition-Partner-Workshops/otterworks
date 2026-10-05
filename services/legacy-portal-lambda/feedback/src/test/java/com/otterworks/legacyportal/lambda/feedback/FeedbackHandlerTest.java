package com.otterworks.legacyportal.lambda.feedback;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.amazonaws.services.lambda.runtime.events.APIGatewayV2HTTPEvent;
import com.amazonaws.services.lambda.runtime.events.APIGatewayV2HTTPResponse;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;

class FeedbackHandlerTest {

    private static final Instant CREATED_AT = Instant.parse("2026-10-05T08:55:00.123456Z");
    private static final Clock FIXED_CLOCK = Clock.fixed(CREATED_AT, ZoneOffset.UTC);
    private static final ObjectMapper EVENT_MAPPER = new ObjectMapper();

    private MemoryFeedbackStore store;
    private FeedbackHandler handler;

    @BeforeEach
    void setUp() {
        store = new MemoryFeedbackStore();
        handler = new FeedbackHandler(new FeedbackService(store, FIXED_CLOCK), FIXED_CLOCK);
    }

    @Test
    void postReturnsCreatedResponseWithStableFieldOrderAndMicros() {
        APIGatewayV2HTTPResponse response = handler.handleRequest(
                event("POST", "/api/feedback", "{\"userId\":\"u-1\",\"rating\":5,\"message\":\"Great\"}",
                        Map.of("Content-Type", "application/json"), Map.of(), false),
                null);

        assertEquals(201, response.getStatusCode());
        assertEquals("application/json", response.getHeaders().get("Content-Type"));
        assertEquals(
                "{\"id\":1,\"userId\":\"u-1\",\"rating\":5,\"message\":\"Great\","
                        + "\"createdAt\":\"2026-10-05T08:55:00.123456Z\"}",
                response.getBody());
        assertEquals(CREATED_AT, store.values.getFirst().createdAt());
    }

    @Test
    void unacceptablePostAcceptReturns406AfterSaving() {
        APIGatewayV2HTTPResponse response = handler.handleRequest(
                event("POST", "/api/feedback", validBody("xml-client"),
                        Map.of("Content-Type", "application/json", "Accept", "application/xml"),
                        Map.of(), false),
                null);

        assertEquals(406, response.getStatusCode());
        assertEquals("", response.getBody());
        assertTrue(response.getHeaders().isEmpty());
        assertEquals(1, store.values.size());
        assertEquals("xml-client", store.values.getFirst().userId());
    }

    @Test
    void acceptableMediaRangeAmongSeveralAllowsJsonResponse() {
        APIGatewayV2HTTPResponse response = handler.handleRequest(
                event("POST", "/api/feedback", validBody("client"),
                        Map.of("Content-Type", "application/json",
                                "Accept", "application/xml, application/json;q=0.9"),
                        Map.of(), false),
                null);

        assertEquals(201, response.getStatusCode());
        assertEquals("application/json", response.getHeaders().get("Content-Type"));
    }

    @Test
    void wildcardAcceptAllowsJsonResponse() {
        APIGatewayV2HTTPResponse response = handler.handleRequest(
                event("POST", "/api/feedback", validBody("client"),
                        Map.of("Content-Type", "application/json", "Accept", "*/*"),
                        Map.of(), false),
                null);

        assertEquals(201, response.getStatusCode());
    }

    @Test
    void unacceptableListAcceptReturns406AfterQuery() {
        APIGatewayV2HTTPResponse response = handler.handleRequest(
                event("GET", "/api/feedback", null, Map.of("Accept", "text/plain"),
                        Map.of("userId", "u"), false),
                null);

        assertEquals(406, response.getStatusCode());
        assertEquals("", response.getBody());
        assertTrue(response.getHeaders().isEmpty());
        assertEquals(1, store.listQueries);
    }

    @Test
    void unacceptableAcceptSuppressesValidationErrorBodyAndHeaders() {
        APIGatewayV2HTTPResponse response = handler.handleRequest(
                event("POST", "/api/feedback", "{\"userId\":\" \",\"rating\":5,\"message\":\"ok\"}",
                        Map.of("Content-Type", "application/json", "Accept", "application/xml"),
                        Map.of(), false),
                null);

        assertEquals(400, response.getStatusCode());
        assertEquals("", response.getBody());
        assertTrue(response.getHeaders().isEmpty());
    }

    @Test
    void unacceptableAcceptSuppressesGlobalExceptionHandlerResponse() {
        store.failSaveWithIllegalArgument = true;
        APIGatewayV2HTTPResponse response = handler.handleRequest(
                event("POST", "/api/feedback", validBody("client"),
                        Map.of("Content-Type", "application/json", "Accept", "application/xml"),
                        Map.of(), false),
                null);

        assertEquals(400, response.getStatusCode());
        assertEquals("", response.getBody());
        assertTrue(response.getHeaders().isEmpty());
    }

    @ParameterizedTest
    @MethodSource("invalidBodies")
    void eachValidationFailureReturnsSpringDefaultBadRequest(String body) {
        APIGatewayV2HTTPResponse response = handler.handleRequest(
                event("POST", "/api/feedback", body,
                        Map.of("Content-Type", "application/json"), Map.of(), false),
                null);

        assertEquals(400, response.getStatusCode());
        assertTrue(response.getBody().contains("\"status\":400"));
        assertTrue(response.getBody().contains("\"error\":\"Bad Request\""));
        assertTrue(response.getBody().contains("\"path\":\"/api/feedback\""));
        assertEquals("application/json", response.getHeaders().get("Content-Type"));
    }

    static List<Arguments> invalidBodies() {
        return List.of(
                Arguments.of("{\"userId\":\"   \",\"rating\":3,\"message\":\"ok\"}"),
                Arguments.of("{\"userId\":\"" + "u".repeat(101) + "\",\"rating\":3,\"message\":\"ok\"}"),
                Arguments.of("{\"userId\":\"u\",\"rating\":0,\"message\":\"ok\"}"),
                Arguments.of("{\"userId\":\"u\",\"rating\":6,\"message\":\"ok\"}"),
                Arguments.of("{\"userId\":\"u\",\"rating\":3,\"message\":\"\"}"),
                Arguments.of("{\"userId\":\"u\",\"rating\":3,\"message\":\""
                        + "m".repeat(2001) + "\"}"),
                Arguments.of("{\"userId\":\"u\",\"rating\":null,\"message\":\"ok\"}"),
                Arguments.of("{\"rating\":3,\"message\":\"ok\"}"),
                Arguments.of("{\"userId\":\"u\",\"rating\":3}"));
    }

    @ParameterizedTest
    @MethodSource("unreadableBodies")
    void unreadableBodiesReturnBadRequest(String body) {
        APIGatewayV2HTTPResponse response = handler.handleRequest(
                event("POST", "/api/feedback", body,
                        Map.of("Content-Type", "application/json"), Map.of(), false),
                null);

        assertEquals(400, response.getStatusCode());
        assertTrue(response.getBody().contains("\"error\":\"Bad Request\""));
    }

    static List<Arguments> unreadableBodies() {
        return List.of(
                Arguments.of(""),
                Arguments.of("{"),
                Arguments.of("null"),
                Arguments.of("[]"),
                Arguments.of("{\"userId\":\"u\",\"rating\":\"five\",\"message\":\"ok\"}"));
    }

    @Test
    void base64BodyIsDecoded() {
        String body = "{\"userId\":\"u-2\",\"rating\":4,\"message\":\"encoded\"}";
        APIGatewayV2HTTPResponse response = handler.handleRequest(
                event("POST", "/api/feedback", Base64.getEncoder().encodeToString(
                                body.getBytes(java.nio.charset.StandardCharsets.UTF_8)),
                        Map.of("Content-Type", "application/json"), Map.of(), true),
                null);

        assertEquals(201, response.getStatusCode());
        assertTrue(response.getBody().contains("\"userId\":\"u-2\""));
    }

    @Test
    void unsupportedOrMissingMediaTypeReturns415() {
        assertEquals(415, handler.handleRequest(
                event("POST", "/api/feedback", "{}", Map.of(), Map.of(), false), null).getStatusCode());
        assertEquals(415, handler.handleRequest(
                event("POST", "/api/feedback", "{}", Map.of("Content-Type", "text/plain"), Map.of(), false),
                null).getStatusCode());
        assertEquals(201, handler.handleRequest(
                event("POST", "/api/feedback", "{\"userId\":\"u\",\"rating\":3,\"message\":\"ok\"}",
                        Map.of("Content-Type", "application/vnd.feedback+json"), Map.of(), false),
                null).getStatusCode());
    }

    @Test
    void listReturnsOnlyUserFeedbackInCreatedAtDescendingOrder() {
        store.values.add(new Feedback(1L, "u", 3, "older",
                Instant.parse("2026-10-04T08:55:00Z")));
        store.values.add(new Feedback(2L, "other", 5, "other",
                Instant.parse("2026-10-06T08:55:00Z")));
        store.values.add(new Feedback(3L, "u", 5, "newer",
                Instant.parse("2026-10-05T08:55:00Z")));

        APIGatewayV2HTTPResponse response = handler.handleRequest(
                event("GET", "/api/feedback", null, Map.of(), Map.of("userId", "u"), false), null);

        assertEquals(200, response.getStatusCode());
        assertEquals(
                "[{\"id\":3,\"userId\":\"u\",\"rating\":5,\"message\":\"newer\","
                        + "\"createdAt\":\"2026-10-05T08:55:00Z\"},"
                        + "{\"id\":1,\"userId\":\"u\",\"rating\":3,\"message\":\"older\","
                        + "\"createdAt\":\"2026-10-04T08:55:00Z\"}]",
                response.getBody());
    }

    @Test
    void missingUserIdIsDefaultBadRequest() {
        APIGatewayV2HTTPResponse response = handler.handleRequest(
                event("GET", "/api/feedback", null, Map.of(), Map.of(), false), null);

        assertEquals(400, response.getStatusCode());
        assertTrue(response.getBody().contains("\"path\":\"/api/feedback\""));
    }

    @Test
    void averageRatingIsZeroWhenEmptyAndUsesDoubleDivision() {
        APIGatewayV2HTTPResponse empty = handler.handleRequest(
                event("GET", "/api/feedback/average-rating", null, Map.of(), Map.of(), false), null);
        assertEquals(200, empty.getStatusCode());
        assertEquals("{\"averageRating\":0.0}", empty.getBody());

        store.values.add(new Feedback(1L, "a", 4, "a", CREATED_AT));
        store.values.add(new Feedback(2L, "b", 5, "b", CREATED_AT));
        store.values.add(new Feedback(3L, "c", 5, "c", CREATED_AT));
        APIGatewayV2HTTPResponse populated = handler.handleRequest(
                event("GET", "/api/feedback/average-rating", null, Map.of(), Map.of(), false), null);
        assertEquals(200, populated.getStatusCode());
        assertEquals("{\"averageRating\":4.666666666666667}", populated.getBody());
    }

    @Test
    void methodsAndPathsFollowSpringMappings() {
        APIGatewayV2HTTPResponse wrongRootMethod = handler.handleRequest(
                event("PUT", "/api/feedback", null, Map.of(), Map.of(), false), null);
        assertEquals(405, wrongRootMethod.getStatusCode());
        assertEquals("GET,POST", wrongRootMethod.getHeaders().get("Allow"));

        APIGatewayV2HTTPResponse wrongAverageMethod = handler.handleRequest(
                event("POST", "/api/feedback/average-rating", "{}", Map.of(), Map.of(), false), null);
        assertEquals(405, wrongAverageMethod.getStatusCode());
        assertEquals("GET", wrongAverageMethod.getHeaders().get("Allow"));

        APIGatewayV2HTTPResponse notFound = handler.handleRequest(
                event("GET", "/api/feedback/nope", null, Map.of(), Map.of(), false), null);
        assertEquals(404, notFound.getStatusCode());
        assertTrue(notFound.getBody().contains("\"error\":\"Not Found\""));

        APIGatewayV2HTTPResponse trailingSlash = handler.handleRequest(
                event("GET", "/api/feedback/", null, Map.of(), Map.of("userId", "u"), false), null);
        assertEquals(200, trailingSlash.getStatusCode());
    }

    @Test
    void optionsAndHeadHaveExpectedEmptyBodies() {
        APIGatewayV2HTTPResponse options = handler.handleRequest(
                event("OPTIONS", "/api/feedback", null, Map.of(), Map.of(), false), null);
        assertEquals(200, options.getStatusCode());
        assertEquals("GET,POST", options.getHeaders().get("Allow"));
        assertEquals("", options.getBody());

        APIGatewayV2HTTPResponse head = handler.handleRequest(
                event("HEAD", "/api/feedback/average-rating", null, Map.of(), Map.of(), false), null);
        assertEquals(200, head.getStatusCode());
        assertEquals("", head.getBody());
        assertEquals("application/json", head.getHeaders().get("Content-Type"));
    }

    @Test
    void serviceKeepsItsIllegalArgumentExceptionGuard() {
        assertEquals("rating must be between 1 and 5",
                assertThrows(IllegalArgumentException.class,
                        () -> new FeedbackService(store, FIXED_CLOCK).submit("u", 6, "bad"))
                        .getMessage());
    }

    private static APIGatewayV2HTTPEvent event(
            String method,
            String path,
            String body,
            Map<String, String> headers,
            Map<String, String> queryParameters,
            boolean base64Encoded) {
        Map<String, Object> http = Map.of("method", method);
        Map<String, Object> requestContext = Map.of("http", http);
        Map<String, Object> event = new LinkedHashMap<>();
        event.put("version", "2.0");
        event.put("rawPath", path);
        event.put("headers", headers);
        event.put("queryStringParameters", queryParameters);
        event.put("requestContext", requestContext);
        event.put("body", body);
        event.put("isBase64Encoded", base64Encoded);
        try {
            return EVENT_MAPPER.readValue(EVENT_MAPPER.writeValueAsString(event),
                    APIGatewayV2HTTPEvent.class);
        } catch (JsonProcessingException exception) {
            throw new AssertionError(exception);
        }
    }

    private static String validBody(String userId) {
        return "{\"userId\":\"" + userId + "\",\"rating\":5,\"message\":\"ok\"}";
    }

    private static final class MemoryFeedbackStore implements FeedbackStore {

        private final List<Feedback> values = new ArrayList<>();
        private int listQueries;
        private boolean failSaveWithIllegalArgument;

        @Override
        public Feedback save(Feedback feedback) {
            if (failSaveWithIllegalArgument) {
                throw new IllegalArgumentException("store rejected feedback");
            }
            Feedback saved = new Feedback((long) (values.size() + 1), feedback.userId(),
                    feedback.rating(), feedback.message(), feedback.createdAt());
            values.add(saved);
            return saved;
        }

        @Override
        public List<Feedback> findByUserIdOrderByCreatedAtDesc(String userId) {
            listQueries++;
            return values.stream()
                    .filter(feedback -> userId.equals(feedback.userId()))
                    .sorted(Comparator.comparing(Feedback::createdAt).reversed())
                    .toList();
        }

        @Override
        public double averageRating() {
            return values.stream().mapToInt(Feedback::rating).average().orElse(0.0);
        }
    }
}
