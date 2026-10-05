package com.otterworks.legacyportal.lambda.announcements;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestHandler;
import com.amazonaws.services.lambda.runtime.events.APIGatewayV2HTTPEvent;
import com.amazonaws.services.lambda.runtime.events.APIGatewayV2HTTPResponse;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.NoSuchElementException;
import java.util.Properties;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.logging.Level;
import java.util.logging.Logger;

public final class Handler implements RequestHandler<APIGatewayV2HTTPEvent, APIGatewayV2HTTPResponse> {
    private static final Pattern SETTING_REFERENCE = Pattern.compile("\\$\\{([^}]+)}");
    private static final DateTimeFormatter DEFAULT_ERROR_TIMESTAMP =
            DateTimeFormatter.ofPattern("uuuu-MM-dd'T'HH:mm:ss.SSSxxx", Locale.ROOT);
    private static final Logger LOGGER = Logger.getLogger(Handler.class.getName());
    private static final ObjectMapper MAPPER = new ObjectMapper()
            .registerModule(new JavaTimeModule())
            .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
    private static final String BANNER = loadBanner();

    private final AnnouncementService service;

    public Handler() {
        this(new DataApiAnnouncementRepository());
    }

    public Handler(AnnouncementRepository repository) {
        this.service = new AnnouncementService(repository);
    }

    @Override
    public APIGatewayV2HTTPResponse handleRequest(APIGatewayV2HTTPEvent event, Context context) {
        String rawPath = requestPath(event);
        String path = routePath(rawPath);
        String method = event.getRequestContext() == null || event.getRequestContext().getHttp() == null
                ? "GET"
                : event.getRequestContext().getHttp().getMethod();
        if (method == null) {
            method = "GET";
        }

        try {
            Object response = dispatch(event, method, path);
            int status = "/api/announcements".equals(path) && "POST".equals(method) ? 201 : 200;
            if (!acceptsJson(event)) {
                return notAcceptable();
            }
            return response(status, response);
        } catch (UnknownRouteException exception) {
            return defaultError(404, "Not Found", rawPath);
        } catch (DefaultErrorException exception) {
            return defaultError(exception.status, exception.reason, rawPath);
        } catch (NoSuchElementException exception) {
            return error(404, "Not Found", exception.getMessage());
        } catch (IllegalArgumentException exception) {
            return error(400, "Bad Request", exception.getMessage());
        } catch (RuntimeException exception) {
            LOGGER.log(Level.SEVERE, "Unhandled announcement request failure", exception);
            return error(500, "Internal Server Error", "Internal Server Error");
        }
    }

    private Object dispatch(APIGatewayV2HTTPEvent event, String method, String path) {
        if ("GET".equals(method) && "/health".equals(path)) {
            Map<String, String> body = new LinkedHashMap<>();
            body.put("status", "UP");
            body.put("service", "legacy-portal");
            body.put("banner", BANNER);
            return body;
        }
        if ("GET".equals(method) && isActuatorHealthPath(path)) {
            if ("/actuator/health".equals(path)) {
                Map<String, Object> health = new LinkedHashMap<>();
                health.put("status", "UP");
                health.put("groups", List.of("liveness", "readiness"));
                return health;
            }
            return Map.of("status", "UP");
        }
        if ("GET".equals(method) && "/actuator/info".equals(path)) {
            return Map.of();
        }
        if (path.startsWith("/api/announcements")) {
            return announcements(event, method, path);
        }
        return notFound();
    }

    private Object announcements(APIGatewayV2HTTPEvent event, String method, String path) {
        if ("/api/announcements".equals(path)) {
            if ("GET".equals(method)) {
                return queryPublishedOnly(event) ? service.listPublished() : service.listAll();
            }
            if ("POST".equals(method)) {
                Charset charset = requestCharset(header(event, "Content-Type"));
                JsonNode body = requestBody(event, charset);
                return service.create(
                        requiredText(body, "title", 200),
                        requiredText(body, "body", 4000),
                        published(body));
            }
            throw new DefaultErrorException(405, "Method Not Allowed");
        }

        Matcher publishMatcher = Pattern.compile("^/api/announcements/([^/]+)/publish$").matcher(path);
        if (publishMatcher.matches()) {
            if (!"POST".equals(method)) {
                throw new DefaultErrorException(405, "Method Not Allowed");
            }
            return service.publish(parseId(publishMatcher.group(1)));
        }

        Matcher idMatcher = Pattern.compile("^/api/announcements/([^/]+)$").matcher(path);
        if (idMatcher.matches()) {
            if (!"GET".equals(method)) {
                throw new DefaultErrorException(405, "Method Not Allowed");
            }
            return service.get(parseId(idMatcher.group(1)));
        }
        return notFound();
    }

    private static boolean isActuatorHealthPath(String path) {
        return "/actuator/health".equals(path)
                || "/actuator/health/liveness".equals(path)
                || "/actuator/health/readiness".equals(path);
    }

    private static boolean queryPublishedOnly(APIGatewayV2HTTPEvent event) {
        Map<String, String> parameters = event.getQueryStringParameters();
        String value = parameters == null ? null : parameters.get("publishedOnly");
        if (value == null || value.isEmpty()) {
            return true;
        }
        String normalized = value.trim().toLowerCase(java.util.Locale.ROOT);
        return switch (normalized) {
            case "true", "on", "yes", "1" -> true;
            case "false", "off", "no", "0" -> false;
            default -> throw new IllegalArgumentException("Invalid boolean value [" + value + "]");
        };
    }

    private static Charset requestCharset(String contentType) {
        if (contentType == null) {
            throw new DefaultErrorException(415, "Unsupported Media Type");
        }
        String[] parts = contentType.split(";");
        String mediaType = parts[0].trim().toLowerCase(Locale.ROOT);
        int separator = mediaType.indexOf('/');
        if (separator < 0 || !"application".equals(mediaType.substring(0, separator))) {
            throw new DefaultErrorException(415, "Unsupported Media Type");
        }
        String subtype = mediaType.substring(separator + 1);
        if (!"json".equals(subtype) && !(subtype.endsWith("+json") && subtype.length() > "+json".length())) {
            throw new DefaultErrorException(415, "Unsupported Media Type");
        }

        for (int i = 1; i < parts.length; i++) {
            String parameter = parts[i].trim();
            int equals = parameter.indexOf('=');
            if (equals > 0 && "charset".equalsIgnoreCase(parameter.substring(0, equals).trim())) {
                String name = parameter.substring(equals + 1).trim();
                if (name.length() >= 2 && name.startsWith("\"") && name.endsWith("\"")) {
                    name = name.substring(1, name.length() - 1);
                }
                try {
                    return Charset.forName(name);
                } catch (IllegalArgumentException exception) {
                    throw new DefaultErrorException(415, "Unsupported Media Type");
                }
            }
        }
        return StandardCharsets.UTF_8;
    }

    private static JsonNode requestBody(APIGatewayV2HTTPEvent event, Charset charset) {
        String body = event.getBody();
        LOGGER.info("Announcement request body from API Gateway: base64Encoded="
                + Boolean.TRUE.equals(event.getIsBase64Encoded())
                + ", bodyLength=" + (body == null ? -1 : body.length()));
        if (body == null) {
            throw new DefaultErrorException(400, "Bad Request");
        }
        if (Boolean.TRUE.equals(event.getIsBase64Encoded())) {
            try {
                body = new String(Base64.getDecoder().decode(body), charset);
            } catch (IllegalArgumentException exception) {
                throw new DefaultErrorException(400, "Bad Request");
            }
        }
        try {
            JsonNode parsed = MAPPER.readTree(body);
            if (parsed == null || !parsed.isObject()) {
                throw new DefaultErrorException(400, "Bad Request");
            }
            return parsed;
        } catch (JsonProcessingException exception) {
            throw new DefaultErrorException(400, "Bad Request");
        }
    }

    private static String requiredText(JsonNode request, String property, int maxLength) {
        JsonNode value = request.get(property);
        if (value == null || value.isNull() || !value.isValueNode()) {
            throw new DefaultErrorException(400, "Bad Request");
        }
        String text = value.asText();
        if (text.isBlank()) {
            throw new DefaultErrorException(400, "Bad Request");
        }
        if (text.length() > maxLength) {
            throw new DefaultErrorException(400, "Bad Request");
        }
        return text;
    }

    private static boolean published(JsonNode request) {
        JsonNode value = request.get("published");
        if (value == null || value.isNull()) {
            return false;
        }
        if (value.isBoolean()) {
            return value.booleanValue();
        }
        if (value.isTextual()) {
            String normalized = value.textValue().trim();
            if ("true".equalsIgnoreCase(normalized)) {
                return true;
            }
            if ("false".equalsIgnoreCase(normalized)) {
                return false;
            }
        } else if (value.isIntegralNumber() && value.canConvertToInt()) {
            if (value.longValue() == 0L) {
                return false;
            }
            if (value.longValue() == 1L) {
                return true;
            }
        }
        throw new DefaultErrorException(400, "Bad Request");
    }

    private static Long parseId(String value) {
        return Long.parseLong(value);
    }

    private static Object notFound() {
        throw new UnknownRouteException();
    }

    private static String routePath(String path) {
        if (path.length() > 1 && path.endsWith("/")) {
            return path.substring(0, path.length() - 1);
        }
        return path;
    }

    private static String requestPath(APIGatewayV2HTTPEvent event) {
        String path = event.getRawPath();
        if (path == null && event.getRequestContext() != null && event.getRequestContext().getHttp() != null) {
            path = event.getRequestContext().getHttp().getPath();
        }
        if (path == null || path.isEmpty()) {
            return "/";
        }
        int querySeparator = path.indexOf('?');
        return querySeparator < 0 ? path : path.substring(0, querySeparator);
    }

    private static APIGatewayV2HTTPResponse defaultError(int status, String reason, String path) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("timestamp", OffsetDateTime.now(ZoneOffset.UTC).format(DEFAULT_ERROR_TIMESTAMP));
        body.put("status", status);
        body.put("error", reason);
        body.put("path", path);
        return response(status, body);
    }

    private static String header(APIGatewayV2HTTPEvent event, String name) {
        Map<String, String> headers = event.getHeaders();
        if (headers == null) {
            return null;
        }
        for (Map.Entry<String, String> entry : headers.entrySet()) {
            if (name.equalsIgnoreCase(entry.getKey())) {
                return entry.getValue();
            }
        }
        return null;
    }

    private static boolean acceptsJson(APIGatewayV2HTTPEvent event) {
        String accept = header(event, "Accept");
        if (accept == null) {
            return true;
        }
        for (String range : accept.split(",")) {
            String[] parts = range.split(";");
            double quality = 1.0;
            for (int i = 1; i < parts.length; i++) {
                String parameter = parts[i].trim();
                int equals = parameter.indexOf('=');
                if (equals > 0 && "q".equalsIgnoreCase(parameter.substring(0, equals).trim())) {
                    try {
                        quality = Double.parseDouble(parameter.substring(equals + 1).trim());
                    } catch (NumberFormatException exception) {
                        quality = 0.0;
                    }
                }
            }
            if (quality <= 0.0 || quality > 1.0 || Double.isNaN(quality)) {
                continue;
            }
            String mediaType = parts[0].trim().toLowerCase(Locale.ROOT);
            int separator = mediaType.indexOf('/');
            if (separator < 0) {
                continue;
            }
            String type = mediaType.substring(0, separator);
            String subtype = mediaType.substring(separator + 1);
            if (("*".equals(type) || "application".equals(type))
                    && ("*".equals(subtype) || "json".equals(subtype) || subtype.endsWith("+json"))) {
                return true;
            }
        }
        return false;
    }

    private static APIGatewayV2HTTPResponse notAcceptable() {
        return APIGatewayV2HTTPResponse.builder()
                .withStatusCode(406)
                .withBody("")
                .withIsBase64Encoded(false)
                .build();
    }

    private static APIGatewayV2HTTPResponse response(int statusCode, Object body) {
        try {
            return APIGatewayV2HTTPResponse.builder()
                    .withStatusCode(statusCode)
                    .withHeaders(Map.of("Content-Type", "application/json"))
                    .withBody(MAPPER.writeValueAsString(body))
                    .withIsBase64Encoded(false)
                    .build();
        } catch (JsonProcessingException exception) {
            return error(500, "Internal Server Error", "Internal Server Error");
        }
    }

    private static APIGatewayV2HTTPResponse error(int status, String reason, String message) {
        Map<String, String> body = new LinkedHashMap<>();
        body.put("error", reason);
        body.put("message", message == null ? reason : message);
        return response(status, body);
    }

    private static String loadBanner() {
        Properties properties = new Properties();
        try (InputStream stream = Handler.class.getClassLoader().getResourceAsStream("portal-settings.properties")) {
            if (stream != null) {
                properties.load(stream);
            }
        } catch (IOException ignored) {
            return "OtterWorks Portal";
        }
        String template = properties.getProperty("portal.banner", "OtterWorks Portal");
        for (int pass = 0; pass < properties.size(); pass++) {
            Matcher matcher = SETTING_REFERENCE.matcher(template);
            StringBuffer resolved = new StringBuffer();
            boolean changed = false;
            while (matcher.find()) {
                String value = properties.getProperty(matcher.group(1));
                if (value == null) {
                    continue;
                }
                matcher.appendReplacement(resolved, Matcher.quoteReplacement(value));
                changed = true;
            }
            matcher.appendTail(resolved);
            template = resolved.toString();
            if (!changed) {
                break;
            }
        }
        return template;
    }

    private static final class DefaultErrorException extends RuntimeException {
        private final int status;
        private final String reason;

        private DefaultErrorException(int status, String reason) {
            this.status = status;
            this.reason = reason;
        }
    }

    private static final class UnknownRouteException extends RuntimeException {
        private UnknownRouteException() {
        }
    }
}
