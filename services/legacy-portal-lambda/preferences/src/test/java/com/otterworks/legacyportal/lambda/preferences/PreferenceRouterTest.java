package com.otterworks.legacyportal.lambda.preferences;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class PreferenceRouterTest {

    private final ObjectMapper objectMapper = new ObjectMapper();
    private InMemoryPreferenceRepository repository;
    private PreferenceRouter router;

    @BeforeEach
    void setUp() {
        repository = new InMemoryPreferenceRepository();
        router = new PreferenceRouter(repository);
    }

    @Test
    void getUnknownUserReturnsDefaults() throws Exception {
        PreferenceRouter.Response response = route("GET", "/api/preferences/alice", Map.of(), null);

        assertEquals(200, response.statusCode());
        assertEquals(
                "{\"userId\":\"alice\",\"theme\":\"light\",\"locale\":\"en-US\","
                        + "\"emailNotifications\":true}",
                response.body());
    }

    @Test
    void putThenGetRoundTripsPreferences() throws Exception {
        PreferenceRouter.Response put =
                route(
                        "PUT",
                        "/api/preferences/alice",
                        jsonHeaders(),
                        "{\"theme\":\"dark\",\"locale\":\"fr-FR\","
                                + "\"emailNotifications\":false}");
        PreferenceRouter.Response get =
                route("GET", "/api/preferences/alice", Map.of(), null);

        assertEquals(200, put.statusCode());
        assertEquals(
                "{\"userId\":\"alice\",\"theme\":\"dark\",\"locale\":\"fr-FR\","
                        + "\"emailNotifications\":false}",
                get.body());
    }

    @Test
    void missingEmailNotificationsDefaultsToFalse() throws Exception {
        PreferenceRouter.Response response =
                route(
                        "PUT",
                        "/api/preferences/alice",
                        jsonHeaders(),
                        "{\"theme\":\"dark\",\"locale\":\"fr-FR\"}");

        assertEquals(200, response.statusCode());
        assertTrue(response.body().endsWith("\"emailNotifications\":false}"));
    }

    @Test
    void blankLocaleReturnsBadRequest() throws Exception {
        assertEquals(
                400,
                route(
                                "PUT",
                                "/api/preferences/alice",
                                jsonHeaders(),
                                "{\"theme\":\"dark\",\"locale\":\"   \"}")
                        .statusCode());
    }

    @Test
    void themeLongerThanTwentyCharactersReturnsBadRequest() throws Exception {
        assertEquals(
                400,
                route(
                                "PUT",
                                "/api/preferences/alice",
                                jsonHeaders(),
                                "{\"theme\":\"123456789012345678901\","
                                        + "\"locale\":\"en-US\"}")
                        .statusCode());
    }

    @Test
    void malformedJsonReturnsBadRequest() throws Exception {
        assertEquals(
                400,
                route("PUT", "/api/preferences/alice", jsonHeaders(), "{not json")
                        .statusCode());
    }

    @Test
    void textPlainContentTypeReturnsUnsupportedMediaType() throws Exception {
        assertEquals(
                415,
                route(
                                "PUT",
                                "/api/preferences/alice",
                                Map.of("Content-Type", "text/plain"),
                                "{\"theme\":\"dark\",\"locale\":\"en-US\"}")
                        .statusCode());
    }

    @Test
    void nonGetOrPutMethodOnMatchedPathReturnsMethodNotAllowed() throws Exception {
        assertEquals(405, route("POST", "/api/preferences/alice", Map.of(), null).statusCode());
        assertEquals(405, route("DELETE", "/api/preferences/alice", Map.of(), null).statusCode());
    }

    @Test
    void decodesEncodedPathVariable() throws Exception {
        PreferenceRouter.Response response =
                route("GET", "/api/preferences/alice%20smith", Map.of(), null);

        assertEquals(200, response.statusCode());
        assertTrue(response.body().contains("\"userId\":\"alice smith\""));
    }

    @Test
    void unsupportedAcceptReturnsEmptyNotAcceptableResponse() throws Exception {
        PreferenceRouter.Response response =
                route(
                        "GET",
                        "/api/preferences/alice",
                        Map.of("Accept", "text/plain"),
                        null);

        assertEquals(406, response.statusCode());
        assertEquals("", response.body());
        assertTrue(response.headers().isEmpty());
    }

    @Test
    void stringBooleanIsCoerced() throws Exception {
        PreferenceRouter.Response response =
                route(
                        "PUT",
                        "/api/preferences/alice",
                        jsonHeaders(),
                        "{\"theme\":\"dark\",\"locale\":\"en-US\","
                                + "\"emailNotifications\":\"true\"}");

        assertEquals(200, response.statusCode());
        assertTrue(response.body().endsWith("\"emailNotifications\":true}"));
    }

    @Test
    void unknownPropertiesAndTrailingTokensAreIgnored() throws Exception {
        PreferenceRouter.Response response =
                route(
                        "PUT",
                        "/api/preferences/alice",
                        jsonHeaders(),
                        "{\"theme\":\"dark\",\"locale\":\"en-US\",\"other\":1} {}");

        assertEquals(200, response.statusCode());
    }

    @Test
    void errorsUseBootStyleJsonAndRawPath() throws Exception {
        PreferenceRouter.Response response =
                route("GET", "/api/preferences/alice/extra", Map.of(), null);
        JsonNode body = objectMapper.readTree(response.body());

        assertEquals(404, response.statusCode());
        assertEquals(404, body.get("status").asInt());
        assertEquals("Not Found", body.get("error").asText());
        assertEquals("/api/preferences/alice/extra", body.get("path").asText());
        assertTrue(body.get("timestamp").asText().matches(
                "\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}\\.\\d{3}\\+00:00"));
        assertFalse(response.headers().isEmpty());
    }

    private PreferenceRouter.Response route(
            String method, String path, Map<String, String> headers, String body) {
        return router.route(method, path, headers, body, false);
    }

    private Map<String, String> jsonHeaders() {
        return Map.of("Content-Type", "application/json");
    }

    private static final class InMemoryPreferenceRepository implements PreferenceRepository {
        private final Map<String, UserPreference> values = new HashMap<>();

        @Override
        public Optional<UserPreference> findById(String userId) {
            return Optional.ofNullable(values.get(userId));
        }

        @Override
        public UserPreference save(UserPreference preference) {
            values.put(preference.userId(), preference);
            return preference;
        }
    }
}
