package com.otterworks.legacyportal.lambda.preferences;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeFormatterBuilder;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.logging.Level;
import java.util.logging.Logger;

public final class PreferenceRouter {

    private static final Logger LOGGER = Logger.getLogger(PreferenceRouter.class.getName());
    private static final Pattern ROUTE = Pattern.compile("^/api/preferences/([^/]+)$");
    private static final DateTimeFormatter TIMESTAMP_FORMAT =
            new DateTimeFormatterBuilder()
                    .appendPattern("yyyy-MM-dd'T'HH:mm:ss.SSS")
                    .appendOffset("+HH:MM", "+00:00")
                    .toFormatter(Locale.ROOT)
                    .withZone(ZoneOffset.UTC);

    private final PreferenceService service;
    private final ObjectMapper objectMapper =
            new ObjectMapper()
                    .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false)
                    .configure(DeserializationFeature.FAIL_ON_TRAILING_TOKENS, false);

    public PreferenceRouter(PreferenceRepository repository) {
        this(new PreferenceService(repository));
    }

    PreferenceRouter(PreferenceService service) {
        this.service = service;
    }

    public Response route(
            String method,
            String rawPath,
            Map<String, String> headers,
            String body,
            boolean isBase64Encoded) {
        String requestPath = rawPath == null ? "" : rawPath;
        Matcher matcher = ROUTE.matcher(requestPath);
        if (!matcher.matches()) {
            return error(404, requestPath);
        }
        if (!"GET".equals(method) && !"PUT".equals(method)) {
            return error(405, requestPath);
        }

        try {
            String userId = decodePathVariable(matcher.group(1));
            PreferenceResponse preference;
            if ("GET".equals(method)) {
                preference = PreferenceResponse.from(service.getOrDefault(userId));
            } else {
                if (!isJsonContentType(header(headers, "content-type"))) {
                    return error(415, requestPath);
                }
                UpdateRequest update = parseUpdate(body, isBase64Encoded);
                validate(update);
                preference =
                        PreferenceResponse.from(
                                service.save(
                                        userId,
                                        update.getTheme(),
                                        update.getLocale(),
                                        update.isEmailNotifications()));
            }

            if (!acceptsJson(header(headers, "accept"))) {
                return new Response(406, Map.of(), "");
            }
            return new Response(
                    200,
                    Map.of("Content-Type", "application/json"),
                    objectMapper.writeValueAsString(preference));
        } catch (BadRequestException | IOException exception) {
            return error(400, requestPath);
        } catch (Exception exception) {
            LOGGER.log(Level.SEVERE, "Unexpected preferences request failure", exception);
            return error(500, requestPath);
        }
    }

    private UpdateRequest parseUpdate(String body, boolean isBase64Encoded)
            throws IOException, BadRequestException {
        if (body == null || body.isBlank()) {
            throw new BadRequestException();
        }
        String json = body;
        if (isBase64Encoded) {
            try {
                json =
                        new String(
                                java.util.Base64.getDecoder().decode(body),
                                StandardCharsets.UTF_8);
            } catch (IllegalArgumentException exception) {
                throw new BadRequestException();
            }
        }
        UpdateRequest request = objectMapper.readValue(json, UpdateRequest.class);
        if (request == null) {
            throw new BadRequestException();
        }
        return request;
    }

    private void validate(UpdateRequest request) throws BadRequestException {
        if (!notBlank(request.getTheme())
                || request.getTheme().length() > 20
                || !notBlank(request.getLocale())
                || request.getLocale().length() > 20) {
            throw new BadRequestException();
        }
    }

    private boolean notBlank(String value) {
        return value != null && !value.isBlank();
    }

    private String decodePathVariable(String value) throws BadRequestException {
        try {
            return URLDecoder.decode(value.replace("+", "%2B"), StandardCharsets.UTF_8);
        } catch (IllegalArgumentException exception) {
            throw new BadRequestException();
        }
    }

    private boolean isJsonContentType(String contentType) {
        if (contentType == null) {
            return false;
        }
        String mediaType = contentType.split(";", 2)[0].trim().toLowerCase(Locale.ROOT);
        return mediaType.equals("application/json")
                || (mediaType.startsWith("application/")
                        && mediaType.endsWith("+json")
                        && mediaType.length() > "application/+json".length());
    }

    private boolean acceptsJson(String accept) {
        if (accept == null) {
            return true;
        }
        for (String range : accept.split(",")) {
            String[] parts = range.trim().split(";");
            String mediaType = parts[0].trim().toLowerCase(Locale.ROOT);
            double quality = 1.0;
            for (int i = 1; i < parts.length; i++) {
                String parameter = parts[i].trim();
                if (parameter.toLowerCase(Locale.ROOT).startsWith("q=")) {
                    try {
                        quality = Double.parseDouble(parameter.substring(2).trim());
                    } catch (NumberFormatException exception) {
                        quality = 0.0;
                    }
                }
            }
            if (quality > 0.0
                    && (mediaType.equals("application/json")
                            || mediaType.equals("application/*")
                            || mediaType.equals("*/*"))) {
                return true;
            }
        }
        return false;
    }

    private String header(Map<String, String> headers, String name) {
        if (headers == null) {
            return null;
        }
        for (Map.Entry<String, String> entry : headers.entrySet()) {
            if (entry.getKey() != null && entry.getKey().equalsIgnoreCase(name)) {
                return entry.getValue();
            }
        }
        return null;
    }

    private Response error(int status, String path) {
        ErrorResponse response =
                new ErrorResponse(
                        TIMESTAMP_FORMAT.format(Instant.now()), status, reason(status), path);
        try {
            return new Response(
                    status,
                    Map.of("Content-Type", "application/json"),
                    objectMapper.writeValueAsString(response));
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException(exception);
        }
    }

    private String reason(int status) {
        return switch (status) {
            case 400 -> "Bad Request";
            case 404 -> "Not Found";
            case 405 -> "Method Not Allowed";
            case 415 -> "Unsupported Media Type";
            default -> "Internal Server Error";
        };
    }

    public record Response(int statusCode, Map<String, String> headers, String body) {
        public Response {
            headers = Map.copyOf(new LinkedHashMap<>(headers));
        }
    }

    public record PreferenceResponse(
            String userId, String theme, String locale, boolean emailNotifications) {
        private static PreferenceResponse from(UserPreference preference) {
            return new PreferenceResponse(
                    preference.userId(),
                    preference.theme(),
                    preference.locale(),
                    preference.emailNotifications());
        }
    }

    private record ErrorResponse(String timestamp, int status, String error, String path) {}

    public static final class UpdateRequest {
        private String theme;
        private String locale;
        private boolean emailNotifications;

        public String getTheme() {
            return theme;
        }

        public void setTheme(String theme) {
            this.theme = theme;
        }

        public String getLocale() {
            return locale;
        }

        public void setLocale(String locale) {
            this.locale = locale;
        }

        public boolean isEmailNotifications() {
            return emailNotifications;
        }

        public void setEmailNotifications(boolean emailNotifications) {
            this.emailNotifications = emailNotifications;
        }
    }

    private static final class BadRequestException extends Exception {}
}
