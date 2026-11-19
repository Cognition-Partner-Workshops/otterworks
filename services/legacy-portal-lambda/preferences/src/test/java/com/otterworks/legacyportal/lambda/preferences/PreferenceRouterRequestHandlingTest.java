package com.otterworks.legacyportal.lambda.preferences;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.HashMap;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Disabled;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

/** Request handling a portal user hits on every settings page load and save. */
class PreferenceRouterRequestHandlingTest {

    private static final String VALID_BODY =
            "{\"theme\":\"dark\",\"locale\":\"fr-FR\",\"emailNotifications\":false}";
    private static final Map<String, String> JSON = Map.of("Content-Type", "application/json");

    private final ObjectMapper objectMapper = new ObjectMapper();
    private RecordingPreferenceRepository repository;
    private PreferenceRouter router;

    @BeforeEach
    void setUp() {
        repository = new RecordingPreferenceRepository();
        router = new PreferenceRouter(repository);
    }

    private PreferenceRouter.Response route(
            String method, String path, Map<String, String> headers, String body) {
        return router.route(method, path, headers, body, false);
    }

    private Map<String, String> headers(String... pairs) {
        Map<String, String> headers = new HashMap<>();
        for (int i = 0; i < pairs.length; i += 2) {
            headers.put(pairs[i], pairs[i + 1]);
        }
        return headers;
    }

    @Nested
    class Persistence {

        @Test
        void savingOneUserDoesNotChangeAnotherUsersPreferences() throws Exception {
            route("PUT", "/api/preferences/u1", JSON, VALID_BODY);
            route(
                    "PUT",
                    "/api/preferences/u2",
                    JSON,
                    "{\"theme\":\"light\",\"locale\":\"de-DE\",\"emailNotifications\":true}");

            JsonNode u1 =
                    objectMapper.readTree(
                            route("GET", "/api/preferences/u1", Map.of(), null).body());
            assertEquals("dark", u1.get("theme").asText());
            assertEquals("fr-FR", u1.get("locale").asText());
            assertFalse(u1.get("emailNotifications").asBoolean());
        }

        @Test
        void secondSaveOverwritesTheFirst() throws Exception {
            route("PUT", "/api/preferences/u1", JSON, VALID_BODY);
            route(
                    "PUT",
                    "/api/preferences/u1",
                    JSON,
                    "{\"theme\":\"light\",\"locale\":\"en-GB\",\"emailNotifications\":true}");

            assertEquals(
                    "{\"userId\":\"u1\",\"theme\":\"light\",\"locale\":\"en-GB\","
                            + "\"emailNotifications\":true}",
                    route("GET", "/api/preferences/u1", Map.of(), null).body());
        }

        @Test
        void putResponseEchoesWhatWasStored() throws Exception {
            PreferenceRouter.Response put = route("PUT", "/api/preferences/u1", JSON, VALID_BODY);

            assertEquals(200, put.statusCode());
            assertEquals("application/json", put.headers().get("Content-Type"));
            assertEquals(
                    "{\"userId\":\"u1\",\"theme\":\"dark\",\"locale\":\"fr-FR\","
                            + "\"emailNotifications\":false}",
                    put.body());
            assertEquals(new UserPreference("u1", "dark", "fr-FR", false), repository.values.get("u1"));
        }

        @Test
        void plusSignInUserIdIsKeptLiterallyNotTurnedIntoASpace() throws Exception {
            route("PUT", "/api/preferences/a+b", JSON, VALID_BODY);

            assertTrue(repository.values.containsKey("a+b"));
            assertFalse(repository.values.containsKey("a b"));
        }

        @Test
        void unacceptableAcceptOnPutStillPersistsTheWriteLikeTheJavaPortal() {
            // Spring MVC (the legacy portal) runs the handler before negotiating the response body,
            // so a PUT with Accept: text/plain is stored and then answered 406. The port keeps that.
            PreferenceRouter.Response put =
                    route(
                            "PUT",
                            "/api/preferences/u1",
                            headers("Content-Type", "application/json", "Accept", "text/plain"),
                            VALID_BODY);

            assertEquals(406, put.statusCode());
            assertEquals(new UserPreference("u1", "dark", "fr-FR", false), repository.values.get("u1"));
        }
    }

    @Nested
    class Validation {

        @ParameterizedTest
        @ValueSource(
                strings = {
                    "{\"locale\":\"en-US\"}",
                    "{\"theme\":null,\"locale\":\"en-US\"}",
                    "{\"theme\":\"\",\"locale\":\"en-US\"}",
                    "{\"theme\":\"dark\"}",
                    "{\"theme\":\"dark\",\"locale\":\"123456789012345678901\"}",
                    "{\"theme\":\"dark\",\"locale\":\"en-US\",\"emailNotifications\":\"maybe\"}",
                    "[]",
                    "null",
                    "\"dark\""
                })
        void invalidUpdatesAreRejectedAndNothingIsWritten(String body) {
            PreferenceRouter.Response response = route("PUT", "/api/preferences/u1", JSON, body);

            assertEquals(400, response.statusCode());
            assertTrue(repository.saves.isEmpty());
        }

        @Test
        void valuesOfExactlyTwentyCharactersAreAccepted() {
            String twenty = "12345678901234567890";
            PreferenceRouter.Response response =
                    route(
                            "PUT",
                            "/api/preferences/u1",
                            JSON,
                            "{\"theme\":\"" + twenty + "\",\"locale\":\"" + twenty + "\"}");

            assertEquals(200, response.statusCode());
            assertEquals(twenty, repository.values.get("u1").theme());
        }

        @ParameterizedTest
        @ValueSource(strings = {"", "   "})
        void missingBodyIsBadRequest(String body) {
            assertEquals(400, route("PUT", "/api/preferences/u1", JSON, body).statusCode());
            assertEquals(400, route("PUT", "/api/preferences/u1", JSON, null).statusCode());
            assertTrue(repository.saves.isEmpty());
        }

        @Test
        void base64EncodedBodyFromApiGatewayIsDecoded() {
            String encoded =
                    Base64.getEncoder().encodeToString(VALID_BODY.getBytes(StandardCharsets.UTF_8));

            PreferenceRouter.Response response =
                    router.route("PUT", "/api/preferences/u1", JSON, encoded, true);

            assertEquals(200, response.statusCode());
            assertEquals("dark", repository.values.get("u1").theme());
        }

        @Test
        void invalidBase64BodyIsBadRequest() {
            PreferenceRouter.Response response =
                    router.route("PUT", "/api/preferences/u1", JSON, "%%%not-base64", true);

            assertEquals(400, response.statusCode());
            assertTrue(repository.saves.isEmpty());
        }

        @Test
        void malformedPercentEncodingInUserIdIsBadRequestNotServerError() {
            assertEquals(400, route("GET", "/api/preferences/a%zz", Map.of(), null).statusCode());
            assertEquals(400, route("PUT", "/api/preferences/a%zz", JSON, VALID_BODY).statusCode());
            assertTrue(repository.saves.isEmpty());
        }
    }

    @Nested
    class ContentNegotiation {

        @ParameterizedTest
        @ValueSource(
                strings = {
                    "application/json; charset=UTF-8",
                    "APPLICATION/JSON",
                    "application/merge-patch+json",
                    "application/vnd.otterworks+json"
                })
        void jsonContentTypeVariantsAreAccepted(String contentType) {
            assertEquals(
                    200,
                    route("PUT", "/api/preferences/u1", headers("content-type", contentType), VALID_BODY)
                            .statusCode());
        }

        @Test
        void missingContentTypeIsUnsupportedMediaTypeAndNothingIsWritten() {
            assertEquals(415, route("PUT", "/api/preferences/u1", Map.of(), VALID_BODY).statusCode());
            assertEquals(415, route("PUT", "/api/preferences/u1", null, VALID_BODY).statusCode());
            assertTrue(repository.saves.isEmpty());
        }

        @Test
        void unsupportedContentTypeIsCheckedBeforeTheBodyIsParsed() {
            assertEquals(
                    415,
                    route("PUT", "/api/preferences/u1", headers("Content-Type", "text/plain"), "{not json")
                            .statusCode());
        }

        @ParameterizedTest
        @ValueSource(
                strings = {
                    "*/*",
                    "application/*",
                    "application/json",
                    "text/html, application/json;q=0.9",
                    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                })
        void browserAndClientAcceptHeadersGetJson(String accept) {
            PreferenceRouter.Response response =
                    route("GET", "/api/preferences/u1", headers("Accept", accept), null);

            assertEquals(200, response.statusCode());
            assertEquals("application/json", response.headers().get("Content-Type"));
        }

        @Test
        void headerNamesAreMatchedCaseInsensitively() {
            assertEquals(
                    406,
                    route("GET", "/api/preferences/u1", headers("ACCEPT", "text/plain"), null)
                            .statusCode());
        }

        @Test
        void nullHeadersOnGetAreTreatedAsAcceptingAnything() {
            assertEquals(200, route("GET", "/api/preferences/u1", null, null).statusCode());
        }
    }

    @Nested
    class Errors {

        @Test
        void databaseFailureOnReadIsA500WithoutLeakingTheCause() throws Exception {
            repository.failFindWith =
                    new IllegalStateException("password authentication failed for user portal");

            PreferenceRouter.Response response = route("GET", "/api/preferences/u1", Map.of(), null);
            JsonNode body = objectMapper.readTree(response.body());

            assertEquals(500, response.statusCode());
            assertEquals(500, body.get("status").asInt());
            assertEquals("Internal Server Error", body.get("error").asText());
            assertEquals("/api/preferences/u1", body.get("path").asText());
            assertFalse(response.body().contains("password"));
            assertEquals(4, body.size());
        }

        @Test
        void databaseFailureOnWriteIsA500NotASuccess() throws Exception {
            repository.failSaveWith = new IllegalStateException("database down");

            PreferenceRouter.Response response = route("PUT", "/api/preferences/u1", JSON, VALID_BODY);

            assertEquals(500, response.statusCode());
            assertEquals(
                    "Internal Server Error", objectMapper.readTree(response.body()).get("error").asText());
        }

        @Test
        void validationErrorsUseTheBootErrorShape() throws Exception {
            PreferenceRouter.Response response =
                    route("PUT", "/api/preferences/u1", JSON, "{\"theme\":\"dark\"}");
            JsonNode body = objectMapper.readTree(response.body());

            assertEquals(400, body.get("status").asInt());
            assertEquals("Bad Request", body.get("error").asText());
            assertEquals("application/json", response.headers().get("Content-Type"));
        }

        @Test
        void unsupportedMediaTypeErrorBody() throws Exception {
            JsonNode body =
                    objectMapper.readTree(
                            route("PUT", "/api/preferences/u1", Map.of(), VALID_BODY).body());

            assertEquals(415, body.get("status").asInt());
            assertEquals("Unsupported Media Type", body.get("error").asText());
        }

        @Test
        void methodNotAllowedErrorBody() throws Exception {
            JsonNode body =
                    objectMapper.readTree(
                            route("PATCH", "/api/preferences/u1", JSON, VALID_BODY).body());

            assertEquals(405, body.get("status").asInt());
            assertEquals("Method Not Allowed", body.get("error").asText());
            assertTrue(repository.saves.isEmpty());
        }

        @ParameterizedTest
        @ValueSource(
                strings = {
                    "/api/preferences",
                    "/api/preferences/",
                    "/API/preferences/u1",
                    "/api/preferences/u1/extra",
                    "/api/preferencesu1"
                })
        void pathsOutsideTheRouteAre404EvenForWrites(String path) {
            assertEquals(404, route("PUT", path, JSON, VALID_BODY).statusCode());
            assertTrue(repository.saves.isEmpty());
        }

        @Test
        void missingPathAndMethodDoNotCrash() throws Exception {
            PreferenceRouter.Response noPath = route("GET", null, Map.of(), null);
            assertEquals(404, noPath.statusCode());
            assertEquals("", objectMapper.readTree(noPath.body()).get("path").asText());

            assertEquals(405, route(null, "/api/preferences/u1", Map.of(), null).statusCode());
        }

        @Test
        void failReadsCanaryFailsEveryGetButNeverBlocksWrites() {
            router = new PreferenceRouter(repository, true);

            assertEquals(500, route("GET", "/no/such/route", Map.of(), null).statusCode());
            assertEquals(405, route("POST", "/api/preferences/u1", JSON, VALID_BODY).statusCode());
            assertEquals(200, route("PUT", "/api/preferences/u1", JSON, VALID_BODY).statusCode());
            assertTrue(repository.lookups.stream().allMatch("u1"::equals));
        }
    }

    /**
     * Behaviour of the Spring Boot 2.7 legacy portal this Lambda replaces (verified with MockMvc
     * against services/legacy-portal on the same revision) that the port does not reproduce. The
     * API Gateway routes are {@code ANY /api/preferences/{proxy+}}, so all of these reach the
     * function.
     */
    @Nested
    class KnownBugs {

        @Test
        @Disabled(
                "BUG: PreferenceRouter.java:24 ROUTE rejects a trailing slash; the legacy portal"
                        + " (Spring trailing-slash matching) answers /api/preferences/u1/ with 200,"
                        + " the Lambda answers 404")
        void trailingSlashIsServedLikeTheLegacyPortal() {
            PreferenceRouter.Response put = route("PUT", "/api/preferences/u1/", JSON, VALID_BODY);
            PreferenceRouter.Response get = route("GET", "/api/preferences/u1/", Map.of(), null);

            assertEquals(200, put.statusCode());
            assertEquals(200, get.statusCode());
            assertTrue(get.body().contains("\"theme\":\"dark\""));
        }

        @Test
        @Disabled(
                "BUG: PreferenceRouter.java:67 only allows GET and PUT; the legacy portal answers"
                        + " HEAD with 200 (implicit for every GET mapping), the Lambda answers 405")
        void headIsAnsweredLikeGet() {
            assertEquals(200, route("HEAD", "/api/preferences/u1", Map.of(), null).statusCode());
        }

        @Test
        @Disabled(
                "BUG: PreferenceRouter.java:161 acceptsJson treats an empty Accept header as"
                        + " accepting nothing; the legacy portal treats it as */* and returns 200,"
                        + " the Lambda returns 406")
        void emptyAcceptHeaderIsTreatedAsAcceptingAnything() {
            assertEquals(
                    200, route("GET", "/api/preferences/u1", headers("Accept", ""), null).statusCode());
        }

        @Test
        @Disabled(
                "BUG: PreferenceRouter.java:161 acceptsJson ignores structured-suffix wildcards;"
                        + " the legacy portal serves Accept: application/*+json with 200, the Lambda"
                        + " returns 406")
        void structuredSuffixWildcardAcceptGetsJson() {
            assertEquals(
                    200,
                    route("GET", "/api/preferences/u1", headers("Accept", "application/*+json"), null)
                            .statusCode());
        }

        @Test
        @Disabled(
                "BUG: PreferenceRouter.java:68 405 responses carry no Allow header; the legacy portal"
                        + " sends Allow: PUT, GET (required by RFC 9110 section 15.5.6)")
        void methodNotAllowedListsTheAllowedMethods() {
            PreferenceRouter.Response response =
                    route("POST", "/api/preferences/u1", JSON, VALID_BODY);

            assertEquals(405, response.statusCode());
            assertTrue(
                    response.headers().keySet().stream().anyMatch("Allow"::equalsIgnoreCase),
                    "405 without Allow header: " + response.headers());
        }
    }
}
