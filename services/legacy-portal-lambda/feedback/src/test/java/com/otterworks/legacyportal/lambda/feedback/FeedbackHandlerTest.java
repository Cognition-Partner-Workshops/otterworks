package com.otterworks.legacyportal.lambda.feedback;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.amazonaws.services.lambda.runtime.events.APIGatewayV2HTTPEvent;
import com.amazonaws.services.lambda.runtime.events.APIGatewayV2HTTPResponse;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Base64;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class FeedbackHandlerTest {
    private static final ObjectMapper JSON = new ObjectMapper();
    private InMemoryRepository repository;
    private FeedbackHandler handler;

    @BeforeEach
    void setUp() {
        repository = new InMemoryRepository();
        handler = new FeedbackHandler(repository);
    }

    @Test
    void createsFeedbackWithOrderedResponseShape() throws Exception {
        APIGatewayV2HTTPResponse response = request("POST", "/api/feedback", null,
                "{\"userId\":\"u1\",\"rating\":5,\"message\":\"great\"}", "application/json", null);

        assertEquals(201, response.getStatusCode());
        assertEquals("application/json", response.getHeaders().get("Content-Type"));
        assertTrue(response.getBody().startsWith("{\"id\":1,\"userId\":\"u1\",\"rating\":5,\"message\":\"great\",\"createdAt\":\""));
        assertTrue(response.getBody().endsWith("\"}"));
        assertEquals(1, repository.rows.size());
    }

    @Test
    void listsRowsNewestFirst() throws Exception {
        repository.save(new Feedback(null, "u1", 2, "older", Instant.parse("2026-10-01T00:00:00Z")));
        repository.save(new Feedback(null, "u1", 4, "newer", Instant.parse("2026-10-02T00:00:00Z")));

        APIGatewayV2HTTPResponse response = request("GET", "/api/feedback", "userId=u1", null, null, null);
        JsonNode body = JSON.readTree(response.getBody());

        assertEquals(200, response.getStatusCode());
        assertEquals("newer", body.get(0).get("message").asText());
        assertEquals("older", body.get(1).get("message").asText());
    }

    @Test
    void emptyUserIdIsValidAndMissingUserIdIsBadRequest() throws Exception {
        APIGatewayV2HTTPResponse empty = request("GET", "/api/feedback", "userId=", null, null, null);
        APIGatewayV2HTTPResponse missing = request("GET", "/api/feedback", null, null, null, null);

        assertEquals(200, empty.getStatusCode());
        assertEquals("[]", empty.getBody());
        assertError(missing, 400, "/api/feedback", "Bad Request");
    }

    @Test
    void averagesMatchJavaDoubleArithmetic() throws Exception {
        assertEquals("{\"averageRating\":0.0}",
                request("GET", "/api/feedback/average-rating", null, null, null, null).getBody());
        repository.save(new Feedback(null, "u", 3, "a", Instant.parse("2026-10-01T00:00:00Z")));
        assertEquals("{\"averageRating\":3.0}",
                request("GET", "/api/feedback/average-rating", null, null, null, null).getBody());
        repository.save(new Feedback(null, "u", 5, "b", Instant.parse("2026-10-02T00:00:00Z")));
        repository.save(new Feedback(null, "u", 1, "c", Instant.parse("2026-10-03T00:00:00Z")));
        assertEquals("{\"averageRating\":3.0}",
                request("GET", "/api/feedback/average-rating", null, null, null, null).getBody());
        repository.save(new Feedback(null, "u", 4, "d", Instant.parse("2026-10-04T00:00:00Z")));
        assertEquals("{\"averageRating\":3.25}",
                request("GET", "/api/feedback/average-rating", null, null, null, null).getBody());
    }

    @Test
    void averagesNineteenOverSixWithExpectedDoubleRendering() throws Exception {
        repository.save(new Feedback(null, "u", 5, "a", Instant.parse("2026-10-01T00:00:00Z")));
        repository.save(new Feedback(null, "u", 3, "b", Instant.parse("2026-10-02T00:00:00Z")));
        repository.save(new Feedback(null, "u", 1, "c", Instant.parse("2026-10-03T00:00:00Z")));
        repository.save(new Feedback(null, "u", 4, "d", Instant.parse("2026-10-04T00:00:00Z")));
        repository.save(new Feedback(null, "u", 4, "e", Instant.parse("2026-10-05T00:00:00Z")));
        repository.save(new Feedback(null, "u", 2, "f", Instant.parse("2026-10-06T00:00:00Z")));

        assertEquals("{\"averageRating\":3.1666666666666665}",
                request("GET", "/api/feedback/average-rating", null, null, null, null).getBody());
    }

    @Test
    void invalidRatingsAndBeanFieldsAreBadRequest() {
        for (String body : List.of(
                "{\"userId\":\"u\",\"rating\":9,\"message\":\"x\"}",
                "{\"userId\":\"u\",\"rating\":0,\"message\":\"x\"}",
                "{\"userId\":\"u\",\"message\":\"x\"}",
                "{\"userId\":\"u\",\"rating\":null,\"message\":\"x\"}",
                "{\"userId\":\"   \",\"rating\":4,\"message\":\"x\"}",
                "{\"userId\":\"u\",\"rating\":4,\"message\":\"   \"}",
                "{\"userId\":\"" + "x".repeat(101) + "\",\"rating\":4,\"message\":\"x\"}")) {
            assertEquals(400, post(body, "application/json", null).getStatusCode(), body);
        }
    }

    @Test
    void jacksonCoercesStringAndFloatingRating() throws Exception {
        APIGatewayV2HTTPResponse stringRating = post(
                "{\"userId\":\"u\",\"rating\":\"4\",\"message\":\"string\"}", "application/json", null);
        APIGatewayV2HTTPResponse floatRating = post(
                "{\"userId\":\"u\",\"rating\":4.7,\"message\":\"float\"}", "application/json", null);

        assertEquals(201, stringRating.getStatusCode());
        assertEquals(4, JSON.readTree(stringRating.getBody()).get("rating").asInt());
        assertEquals(201, floatRating.getStatusCode());
        assertEquals(4, JSON.readTree(floatRating.getBody()).get("rating").asInt());
    }

    @Test
    void malformedJsonAndUnsupportedContentTypeAreRejected() {
        assertEquals(400, post("{\"userId\":", "application/json", null).getStatusCode());
        assertEquals(415, post("rating=5", "text/plain", null).getStatusCode());
        assertEquals(415, request("POST", "/api/feedback", null,
                "{\"userId\":\"u\",\"rating\":1,\"message\":\"x\"}", null, null).getStatusCode());
    }

    @Test
    void wrongMethodAndUnknownPathUseSpringErrorShapes() {
        APIGatewayV2HTTPResponse method = request("DELETE", "/api/feedback", null, null, null, null);
        APIGatewayV2HTTPResponse averageMethod = request("POST", "/api/feedback/average-rating",
                null, null, null, null);
        APIGatewayV2HTTPResponse path = request("GET", "/api/feedback/Average-Rating", null, null, null, null);

        assertError(method, 405, "/api/feedback", "Method Not Allowed");
        assertNotNull(method.getHeaders().get("Allow"));
        assertError(averageMethod, 405, "/api/feedback/average-rating", "Method Not Allowed");
        assertError(path, 404, "/api/feedback/Average-Rating", "Not Found");
    }

    @Test
    void unacceptableAcceptIsCheckedAfterPostHasBeenSaved() {
        APIGatewayV2HTTPResponse response = post(
                "{\"userId\":\"xml\",\"rating\":5,\"message\":\"saved\"}", "application/json", "application/xml");

        assertEquals(406, response.getStatusCode());
        assertEquals("", response.getBody());
        assertFalse(response.getHeaders().containsKey("Content-Type"));
        assertEquals(1, repository.rows.size());
    }

    @Test
    void acceptsJsonMediaRangesAndRejectsExplicitZeroQuality() {
        assertEquals(201, post("{\"userId\":\"u\",\"rating\":2,\"message\":\"x\"}",
                "application/problem+json; charset=utf-8", "application/*;q=0.8").getStatusCode());
        assertEquals(406, post("{\"userId\":\"u\",\"rating\":2,\"message\":\"x\"}",
                "application/json", "application/json;q=0, */*;q=1").getStatusCode());
        assertEquals(201, post("{\"userId\":\"u\",\"rating\":2,\"message\":\"x\"}",
                "application/json", "application/json;q=0.8, application/xml;q=1").getStatusCode());
    }

    @Test
    void supportsTrailingSlashAndFirstDecodedQueryValue() throws Exception {
        APIGatewayV2HTTPResponse created = request("POST", "/api/feedback/", null,
                "{\"userId\":\"a b\",\"rating\":1,\"message\":\"x\"}", "application/json", null);
        APIGatewayV2HTTPResponse listed = request("GET", "/api/feedback", "userId=a+b&userId=other", null, null, null);

        assertEquals(201, created.getStatusCode());
        assertEquals("a b", JSON.readTree(listed.getBody()).get(0).get("userId").asText());
    }

    @Test
    void decodesBase64BodyBeforeJsonBinding() throws Exception {
        String json = "{\"userId\":\"u\",\"rating\":3,\"message\":\"encoded\"}";
        String encoded = Base64.getEncoder().encodeToString(json.getBytes(StandardCharsets.UTF_8));
        APIGatewayV2HTTPResponse response = request("POST", "/api/feedback", null, encoded,
                "application/json", null, true);

        assertEquals(201, response.getStatusCode());
        assertEquals("encoded", JSON.readTree(response.getBody()).get("message").asText());
    }

    @Test
    void unknownJsonFieldsAreIgnoredAndNullRatingDefaultsToZero() throws Exception {
        APIGatewayV2HTTPResponse unknown = post(
                "{\"userId\":\"u\",\"rating\":2,\"message\":\"x\",\"extra\":true}", "application/json", null);
        APIGatewayV2HTTPResponse nullRating = post(
                "{\"userId\":\"u\",\"rating\":null,\"message\":\"x\"}", "application/json", null);

        assertEquals(201, unknown.getStatusCode());
        assertEquals(400, nullRating.getStatusCode());
    }

    private APIGatewayV2HTTPResponse post(String body, String contentType, String accept) {
        return request("POST", "/api/feedback", null, body, contentType, accept);
    }

    private APIGatewayV2HTTPResponse request(
            String method, String path, String rawQuery, String body, String contentType, String accept) {
        return request(method, path, rawQuery, body, contentType, accept, false);
    }

    private APIGatewayV2HTTPResponse request(
            String method, String path, String rawQuery, String body, String contentType, String accept, boolean base64) {
        APIGatewayV2HTTPEvent.RequestContext.Http http = new APIGatewayV2HTTPEvent.RequestContext.Http();
        http.setMethod(method);
        APIGatewayV2HTTPEvent.RequestContext context = new APIGatewayV2HTTPEvent.RequestContext();
        context.setHttp(http);
        APIGatewayV2HTTPEvent event = new APIGatewayV2HTTPEvent();
        event.setRawPath(path);
        event.setRawQueryString(rawQuery);
        event.setRequestContext(context);
        event.setBody(body);
        event.setIsBase64Encoded(base64);
        Map<String, String> headers = new HashMap<>();
        if (contentType != null) {
            headers.put("Content-Type", contentType);
        }
        if (accept != null) {
            headers.put("Accept", accept);
        }
        event.setHeaders(headers);
        return handler.handleRequest(event, null);
    }

    private static void assertError(
            APIGatewayV2HTTPResponse response, int status, String path, String reason) {
        assertEquals(status, response.getStatusCode());
        assertEquals("application/json", response.getHeaders().get("Content-Type"));
        try {
            JsonNode body = JSON.readTree(response.getBody());
            assertEquals(List.of("timestamp", "status", "error", "path"),
                    iterableNames(body.fieldNames()));
            assertTrue(body.get("timestamp").asText().matches(
                    "\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}\\.\\d{3}\\+00:00"));
            assertEquals(status, body.get("status").asInt());
            assertEquals(reason, body.get("error").asText());
            assertEquals(path, body.get("path").asText());
        } catch (Exception exception) {
            throw new AssertionError(exception);
        }
    }

    private static List<String> iterableNames(java.util.Iterator<String> names) {
        List<String> values = new ArrayList<>();
        names.forEachRemaining(values::add);
        return values;
    }

    private static final class InMemoryRepository implements FeedbackRepository {
        private final List<Feedback> rows = new ArrayList<>();
        private long nextId = 1;

        @Override
        public Feedback save(Feedback feedback) {
            Feedback persisted = new Feedback(
                    nextId++, feedback.userId(), feedback.rating(), feedback.message(), feedback.createdAt());
            rows.add(persisted);
            return persisted;
        }

        @Override
        public List<Feedback> findByUserId(String userId) {
            return rows.stream()
                    .filter(row -> row.userId().equals(userId))
                    .sorted(Comparator.comparing(Feedback::createdAt).thenComparing(Feedback::id).reversed())
                    .toList();
        }

        @Override
        public FeedbackAggregates aggregate() {
            long sum = rows.stream().mapToLong(Feedback::rating).sum();
            return new FeedbackAggregates(rows.size(), sum);
        }
    }
}
