package com.otterworks.legacyportal.lambda.preferences;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestStreamHandler;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.TreeMap;

public class PreferencesHandler implements RequestStreamHandler {

    private static final ObjectMapper MAPPER =
            new ObjectMapper()
                    .disable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES);
    private static final DateTimeFormatter ERROR_TIMESTAMP =
            DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss.SSS'+00:00'");
    private static final String ROUTE_PREFIX = "/api/preferences/";

    static final String DEFAULT_THEME = "light";
    static final String DEFAULT_LOCALE = "en-US";

    private volatile PreferenceRepository repository;

    public PreferencesHandler() {}

    PreferencesHandler(PreferenceRepository repository) {
        this.repository = repository;
    }

    private PreferenceRepository repository() {
        if (repository == null) {
            synchronized (this) {
                if (repository == null) {
                    repository = new DataApiPreferenceRepository();
                }
            }
        }
        return repository;
    }

    @Override
    public void handleRequest(InputStream input, OutputStream output, Context context)
            throws IOException {
        JsonNode event = MAPPER.readTree(input);

        String rawPath = textOr(event.get("rawPath"), "");
        String method = textOr(event.at("/requestContext/http/method"), "").toUpperCase(Locale.ROOT);
        Map<String, String> headers = headers(event.get("headers"));
        String body = body(event);

        ObjectNode response = route(rawPath, method, headers, body);
        MAPPER.writeValue(output, response);
    }

    private ObjectNode route(
            String rawPath, String method, Map<String, String> headers, String body) {
        if (!rawPath.startsWith(ROUTE_PREFIX)) {
            return error(404, "Not Found", rawPath);
        }
        String segment = rawPath.substring(ROUTE_PREFIX.length());
        if (segment.isEmpty() || segment.indexOf('/') >= 0) {
            return error(404, "Not Found", rawPath);
        }
        String userId;
        try {
            userId = URLDecoder.decode(segment.replace("+", "%2B"), StandardCharsets.UTF_8);
        } catch (IllegalArgumentException e) {
            return error(400, "Bad Request", rawPath);
        }

        switch (method) {
            case "GET":
            case "HEAD":
                return get(userId, headers, rawPath, "HEAD".equals(method));
            case "PUT":
                return put(userId, headers, rawPath, body);
            default:
                return error(405, "Method Not Allowed", rawPath);
        }
    }

    private ObjectNode get(
            String userId, Map<String, String> headers, String rawPath, boolean headOnly) {
        if (!acceptsJson(headers.get("accept"))) {
            return notAcceptable();
        }
        UserPreference preference = repository().findById(userId)
                .orElseGet(
                        () -> new UserPreference(userId, DEFAULT_THEME, DEFAULT_LOCALE, true));
        return ok(preference, headOnly);
    }

    private ObjectNode put(
            String userId, Map<String, String> headers, String rawPath, String body) {
        if (!isJsonContentType(headers.get("content-type"))) {
            return error(415, "Unsupported Media Type", rawPath);
        }
        if (body == null || body.isEmpty()) {
            return error(400, "Bad Request", rawPath);
        }
        UpdatePreferenceRequest request;
        try {
            request = MAPPER.readValue(body, UpdatePreferenceRequest.class);
        } catch (Exception e) {
            return error(400, "Bad Request", rawPath);
        }
        if (request == null || isBlank(request.getTheme()) || isBlank(request.getLocale())
                || request.getTheme().length() > 20 || request.getLocale().length() > 20) {
            return error(400, "Bad Request", rawPath);
        }
        if (!acceptsJson(headers.get("accept"))) {
            return notAcceptable();
        }
        UserPreference preference = repository().findById(userId)
                .orElseGet(
                        () -> new UserPreference(userId, DEFAULT_THEME, DEFAULT_LOCALE, true));
        preference.setTheme(request.getTheme());
        preference.setLocale(request.getLocale());
        preference.setEmailNotifications(request.isEmailNotifications());
        repository().save(preference);
        return ok(preference, false);
    }

    private ObjectNode ok(UserPreference preference, boolean emptyBody) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("userId", preference.getUserId());
        payload.put("theme", preference.getTheme());
        payload.put("locale", preference.getLocale());
        payload.put("emailNotifications", preference.isEmailNotifications());
        try {
            return response(
                    200,
                    "application/json",
                    emptyBody ? "" : MAPPER.writeValueAsString(payload));
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    private ObjectNode error(int status, String reason, String rawPath) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put(
                "timestamp",
                OffsetDateTime.now(ZoneOffset.UTC).format(ERROR_TIMESTAMP));
        payload.put("status", status);
        payload.put("error", reason);
        payload.put("path", rawPath);
        try {
            return response(status, "application/json", MAPPER.writeValueAsString(payload));
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    private ObjectNode notAcceptable() {
        ObjectNode node = MAPPER.createObjectNode();
        node.put("statusCode", 406);
        node.putObject("headers");
        node.put("body", "");
        node.put("isBase64Encoded", false);
        return node;
    }

    private ObjectNode response(int status, String contentType, String body) {
        ObjectNode node = MAPPER.createObjectNode();
        node.put("statusCode", status);
        node.putObject("headers").put("Content-Type", contentType);
        node.put("body", body);
        node.put("isBase64Encoded", false);
        return node;
    }

    private static boolean isBlank(String value) {
        return value == null || value.trim().isEmpty();
    }

    private static boolean isJsonContentType(String contentType) {
        if (contentType == null) {
            return false;
        }
        String mediaType = contentType.split(";", 2)[0].trim().toLowerCase(Locale.ROOT);
        if (mediaType.equals("application/json")) {
            return true;
        }
        return mediaType.startsWith("application/") && mediaType.endsWith("+json");
    }

    private static boolean acceptsJson(String accept) {
        if (accept == null || accept.trim().isEmpty()) {
            return true;
        }
        for (String part : accept.split(",")) {
            String mediaType = part.split(";", 2)[0].trim().toLowerCase(Locale.ROOT);
            if (mediaType.equals("application/json")
                    || mediaType.equals("*/*")
                    || mediaType.equals("application/*")) {
                return true;
            }
        }
        return false;
    }

    private static String body(JsonNode event) {
        JsonNode bodyNode = event.get("body");
        if (bodyNode == null || bodyNode.isNull()) {
            return null;
        }
        String body = bodyNode.asText();
        if (event.path("isBase64Encoded").asBoolean(false)) {
            body = new String(Base64.getDecoder().decode(body), StandardCharsets.UTF_8);
        }
        return body;
    }

    private static Map<String, String> headers(JsonNode node) {
        Map<String, String> headers = new TreeMap<>();
        if (node != null && node.isObject()) {
            node.fields()
                    .forEachRemaining(
                            e -> headers.put(
                                    e.getKey().toLowerCase(Locale.ROOT), e.getValue().asText()));
        }
        return headers;
    }

    private static String textOr(JsonNode node, String fallback) {
        return node == null || node.isNull() ? fallback : node.asText();
    }
}
