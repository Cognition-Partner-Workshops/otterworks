package com.otterworks.legacyportal.lambda.preferences;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class PreferencesHandlerTest {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private InMemoryRepository repository;
    private PreferencesHandler handler;

    static class InMemoryRepository implements PreferenceRepository {
        private final Map<String, UserPreference> store = new HashMap<>();
        int saves;

        @Override
        public Optional<UserPreference> findById(String userId) {
            return Optional.ofNullable(store.get(userId));
        }

        @Override
        public UserPreference save(UserPreference preference) {
            store.put(preference.getUserId(), preference);
            saves++;
            return preference;
        }
    }

    @BeforeEach
    void setUp() {
        repository = new InMemoryRepository();
        handler = new PreferencesHandler(repository);
    }

    private JsonNode invoke(String method, String rawPath, Map<String, String> headers, String body)
            throws Exception {
        Map<String, Object> event = new LinkedHashMap<>();
        event.put("version", "2.0");
        event.put("rawPath", rawPath);
        Map<String, Object> requestContext = new LinkedHashMap<>();
        requestContext.put("http", Map.of("method", method, "path", rawPath));
        event.put("requestContext", requestContext);
        event.put("headers", headers);
        if (body != null) {
            event.put("body", body);
        }
        event.put("isBase64Encoded", false);
        byte[] input = MAPPER.writeValueAsBytes(event);
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        handler.handleRequest(new ByteArrayInputStream(input), output, null);
        return MAPPER.readTree(output.toByteArray());
    }

    private Map<String, String> headers(String... pairs) {
        Map<String, String> headers = new LinkedHashMap<>();
        for (int i = 0; i < pairs.length; i += 2) {
            headers.put(pairs[i], pairs[i + 1]);
        }
        return headers;
    }

    @Test
    void getUnknownUserReturnsDefaultsWithoutPersisting() throws Exception {
        JsonNode response = invoke("GET", "/api/preferences/alice", headers(), null);
        assertEquals(200, response.get("statusCode").asInt());
        JsonNode body = MAPPER.readTree(response.get("body").asText());
        assertEquals("alice", body.get("userId").asText());
        assertEquals("light", body.get("theme").asText());
        assertEquals("en-US", body.get("locale").asText());
        assertTrue(body.get("emailNotifications").asBoolean());
        assertEquals(0, repository.saves);
    }

    @Test
    void putThenGetRoundTrips() throws Exception {
        JsonNode put = invoke(
                "PUT",
                "/api/preferences/bob",
                headers("Content-Type", "application/json"),
                "{\"theme\":\"dark\",\"locale\":\"fr-FR\",\"emailNotifications\":false}");
        assertEquals(200, put.get("statusCode").asInt());
        JsonNode get = invoke("GET", "/api/preferences/bob", headers(), null);
        JsonNode body = MAPPER.readTree(get.get("body").asText());
        assertEquals("dark", body.get("theme").asText());
        assertEquals("fr-FR", body.get("locale").asText());
        assertFalse(body.get("emailNotifications").asBoolean());
    }

    @Test
    void omittedEmailNotificationsIsFalse() throws Exception {
        JsonNode response = invoke(
                "PUT",
                "/api/preferences/cara",
                headers("Content-Type", "application/json"),
                "{\"theme\":\"dark\",\"locale\":\"de-DE\"}");
        JsonNode body = MAPPER.readTree(response.get("body").asText());
        assertFalse(body.get("emailNotifications").asBoolean());
    }

    @Test
    void stringEmailNotificationsCoercesToTrue() throws Exception {
        JsonNode response = invoke(
                "PUT",
                "/api/preferences/dan",
                headers("Content-Type", "application/json"),
                "{\"theme\":\"dark\",\"locale\":\"de-DE\",\"emailNotifications\":\"true\"}");
        JsonNode body = MAPPER.readTree(response.get("body").asText());
        assertTrue(body.get("emailNotifications").asBoolean());
    }

    @Test
    void missingThemeIsBadRequest() throws Exception {
        JsonNode response = invoke(
                "PUT",
                "/api/preferences/eve",
                headers("Content-Type", "application/json"),
                "{\"locale\":\"en-US\"}");
        assertEquals(400, response.get("statusCode").asInt());
        JsonNode body = MAPPER.readTree(response.get("body").asText());
        assertEquals("Bad Request", body.get("error").asText());
        assertEquals("/api/preferences/eve", body.get("path").asText());
        assertTrue(
                body.get("timestamp")
                        .asText()
                        .matches("^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}\\.\\d{3}\\+00:00$"));
    }

    @Test
    void overlongThemeIsBadRequest() throws Exception {
        JsonNode response = invoke(
                "PUT",
                "/api/preferences/eve",
                headers("Content-Type", "application/json"),
                "{\"theme\":\"abcdefghijklmnopqrstu\",\"locale\":\"en-US\"}");
        assertEquals(400, response.get("statusCode").asInt());
    }

    @Test
    void whitespaceLocaleIsBadRequest() throws Exception {
        JsonNode response = invoke(
                "PUT",
                "/api/preferences/eve",
                headers("Content-Type", "application/json"),
                "{\"theme\":\"dark\",\"locale\":\"   \"}");
        assertEquals(400, response.get("statusCode").asInt());
    }

    @Test
    void malformedJsonIsBadRequest() throws Exception {
        JsonNode response = invoke(
                "PUT",
                "/api/preferences/eve",
                headers("Content-Type", "application/json"),
                "{not json");
        assertEquals(400, response.get("statusCode").asInt());
    }

    @Test
    void textPlainIsUnsupportedMediaType() throws Exception {
        JsonNode response = invoke(
                "PUT",
                "/api/preferences/eve",
                headers("Content-Type", "text/plain"),
                "{\"theme\":\"dark\",\"locale\":\"en-US\"}");
        assertEquals(415, response.get("statusCode").asInt());
        JsonNode body = MAPPER.readTree(response.get("body").asText());
        assertEquals("Unsupported Media Type", body.get("error").asText());
    }

    @Test
    void postAndDeleteAreMethodNotAllowed() throws Exception {
        assertEquals(
                405,
                invoke("POST", "/api/preferences/eve", headers(), null)
                        .get("statusCode")
                        .asInt());
        assertEquals(
                405,
                invoke("DELETE", "/api/preferences/eve", headers(), null)
                        .get("statusCode")
                        .asInt());
    }

    @Test
    void bareCollectionPathIsNotFound() throws Exception {
        JsonNode response = invoke("GET", "/api/preferences/", headers(), null);
        assertEquals(404, response.get("statusCode").asInt());
        JsonNode body = MAPPER.readTree(response.get("body").asText());
        assertEquals("Not Found", body.get("error").asText());
    }

    @Test
    void percentEncodedUserIdIsDecoded() throws Exception {
        JsonNode response = invoke("GET", "/api/preferences/al%20ice", headers(), null);
        JsonNode body = MAPPER.readTree(response.get("body").asText());
        assertEquals("al ice", body.get("userId").asText());
    }

    @Test
    void unacceptableAcceptHeaderIsNotAcceptable() throws Exception {
        JsonNode response =
                invoke("GET", "/api/preferences/alice", headers("Accept", "text/plain"), null);
        assertEquals(406, response.get("statusCode").asInt());
        assertEquals("", response.get("body").asText());
        assertNull(response.get("headers").get("Content-Type"));
    }

    @Test
    void headBehavesLikeGetWithoutBody() throws Exception {
        JsonNode response = invoke("HEAD", "/api/preferences/alice", headers(), null);
        assertEquals(200, response.get("statusCode").asInt());
        assertEquals("", response.get("body").asText());
    }
}
