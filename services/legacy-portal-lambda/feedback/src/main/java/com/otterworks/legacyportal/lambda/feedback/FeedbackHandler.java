package com.otterworks.legacyportal.lambda.feedback;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestHandler;
import com.amazonaws.services.lambda.runtime.events.APIGatewayV2HTTPEvent;
import com.amazonaws.services.lambda.runtime.events.APIGatewayV2HTTPResponse;
import com.fasterxml.jackson.annotation.JsonPropertyOrder;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

public class FeedbackHandler
        implements RequestHandler<APIGatewayV2HTTPEvent, APIGatewayV2HTTPResponse> {

    private static final String BASE_PATH = "/api/feedback";
    private static final String AVERAGE_PATH = BASE_PATH + "/average-rating";
    private static final String JSON_CONTENT_TYPE = "application/json";
    private static final DateTimeFormatter ERROR_TIMESTAMP_FORMAT =
            DateTimeFormatter.ofPattern("uuuu-MM-dd'T'HH:mm:ss.SSS", Locale.ROOT);
    private static final ObjectMapper MAPPER = createMapper();

    private final FeedbackService service;
    private final Clock clock;

    public FeedbackHandler() {
        this(new FeedbackService(new DataApiFeedbackStore(System.getenv())), Clock.systemUTC());
    }

    FeedbackHandler(FeedbackService service, Clock clock) {
        this.service = service;
        this.clock = clock;
    }

    @Override
    public APIGatewayV2HTTPResponse handleRequest(APIGatewayV2HTTPEvent event, Context context) {
        String path = requestPath(event);
        String method = requestMethod(event);
        String normalizedPath = normalizePath(path);
        List<String> allowedMethods = allowedMethods(normalizedPath);

        if (allowedMethods == null) {
            return defaultError(event, 404, "Not Found", path);
        }
        if ("OPTIONS".equals(method)) {
            return response(200, "", Map.of("Allow", String.join(",", allowedMethods)));
        }
        if ("HEAD".equals(method)
                && (BASE_PATH.equals(normalizedPath) || AVERAGE_PATH.equals(normalizedPath))) {
            APIGatewayV2HTTPResponse getResponse = dispatchGet(event, normalizedPath, path);
            getResponse.setBody("");
            return getResponse;
        }
        if (("GET".equals(method) && BASE_PATH.equals(normalizedPath))
                || ("GET".equals(method) && AVERAGE_PATH.equals(normalizedPath))) {
            return dispatchGet(event, normalizedPath, path);
        }
        if ("POST".equals(method) && BASE_PATH.equals(normalizedPath)) {
            try {
                return submit(event, path);
            } catch (UnreadableBodyException | InvalidRequestException exception) {
                return defaultError(event, 400, "Bad Request", path);
            } catch (IllegalArgumentException exception) {
                return globalError(event, 400, "Bad Request", exception.getMessage());
            } catch (RuntimeException exception) {
                return defaultError(event, 500, "Internal Server Error", path);
            }
        }
        if (allowedMethods.contains(method) || "HEAD".equals(method)) {
            return defaultError(event, 405, "Method Not Allowed", path,
                    Map.of("Allow", String.join(",", allowedMethods)));
        }
        return defaultError(event, 405, "Method Not Allowed", path,
                Map.of("Allow", String.join(",", allowedMethods)));
    }

    private APIGatewayV2HTTPResponse dispatchGet(
            APIGatewayV2HTTPEvent event, String normalizedPath, String path) {
        try {
            if (AVERAGE_PATH.equals(normalizedPath)) {
                return successJsonResponse(
                        event, 200, new AverageRatingResponse(service.averageRating()));
            }
            Map<String, String> queryParameters = event == null ? null : event.getQueryStringParameters();
            String userId = queryParameters == null ? null : queryParameters.get("userId");
            if (userId == null) {
                return defaultError(event, 400, "Bad Request", path);
            }
            List<FeedbackResponse> feedback = service.listForUser(userId).stream()
                    .map(FeedbackResponse::from)
                    .toList();
            return successJsonResponse(event, 200, feedback);
        } catch (RuntimeException exception) {
            return defaultError(event, 500, "Internal Server Error", path);
        }
    }

    private APIGatewayV2HTTPResponse submit(APIGatewayV2HTTPEvent event, String path) {
        if (!hasJsonContentType(event)) {
            return defaultError(event, 415, "Unsupported Media Type", path);
        }
        String body = event == null ? null : event.getBody();
        if (body == null || body.isEmpty()) {
            throw new UnreadableBodyException();
        }
        if (event.getIsBase64Encoded()) {
            try {
                body = new String(Base64.getDecoder().decode(body), StandardCharsets.UTF_8);
            } catch (IllegalArgumentException exception) {
                throw new UnreadableBodyException();
            }
        }

        SubmitFeedbackRequest request;
        try {
            if (!MAPPER.readTree(body).isObject()) {
                throw new UnreadableBodyException();
            }
            request = MAPPER.readValue(body, SubmitFeedbackRequest.class);
        } catch (JsonProcessingException | IllegalArgumentException exception) {
            throw new UnreadableBodyException();
        }
        if (request == null) {
            throw new UnreadableBodyException();
        }
        if (!isValid(request)) {
            throw new InvalidRequestException();
        }
        Feedback saved = service.submit(request.getUserId(), request.getRating(), request.getMessage());
        return successJsonResponse(event, 201, FeedbackResponse.from(saved));
    }

    private APIGatewayV2HTTPResponse defaultError(
            APIGatewayV2HTTPEvent event, int status, String reason, String path) {
        return defaultError(event, status, reason, path, Map.of());
    }

    private APIGatewayV2HTTPResponse defaultError(
            APIGatewayV2HTTPEvent event,
            int status,
            String reason,
            String path,
            Map<String, String> extraHeaders) {
        if (!acceptsJson(event)) {
            return emptyResponse(status);
        }
        LinkedHashMap<String, Object> error = new LinkedHashMap<>();
        Instant now = Instant.now(clock);
        error.put("timestamp", ERROR_TIMESTAMP_FORMAT.withZone(ZoneOffset.UTC).format(now) + "+00:00");
        error.put("status", status);
        error.put("error", reason);
        error.put("path", path);
        return jsonResponse(status, error, extraHeaders);
    }

    private APIGatewayV2HTTPResponse globalError(
            APIGatewayV2HTTPEvent event, int status, String reason, String message) {
        if (!acceptsJson(event)) {
            return emptyResponse(status);
        }
        LinkedHashMap<String, String> error = new LinkedHashMap<>();
        error.put("error", reason);
        error.put("message", message);
        return jsonResponse(status, error);
    }

    private APIGatewayV2HTTPResponse successJsonResponse(
            APIGatewayV2HTTPEvent event, int status, Object body) {
        return acceptsJson(event) ? jsonResponse(status, body) : emptyResponse(406);
    }

    private APIGatewayV2HTTPResponse jsonResponse(int status, Object body) {
        return jsonResponse(status, body, Map.of());
    }

    private APIGatewayV2HTTPResponse jsonResponse(
            int status, Object body, Map<String, String> extraHeaders) {
        try {
            return response(status, MAPPER.writeValueAsString(body), extraHeaders);
        } catch (JsonProcessingException exception) {
            return response(500, "{\"status\":500,\"error\":\"Internal Server Error\"}", Map.of());
        }
    }

    private APIGatewayV2HTTPResponse response(
            int status, String body, Map<String, String> extraHeaders) {
        APIGatewayV2HTTPResponse response = new APIGatewayV2HTTPResponse();
        response.setStatusCode(status);
        LinkedHashMap<String, String> headers = new LinkedHashMap<>();
        headers.put("Content-Type", JSON_CONTENT_TYPE);
        headers.putAll(extraHeaders);
        response.setHeaders(headers);
        response.setBody(body);
        response.setIsBase64Encoded(false);
        return response;
    }

    private APIGatewayV2HTTPResponse emptyResponse(int status) {
        APIGatewayV2HTTPResponse response = new APIGatewayV2HTTPResponse();
        response.setStatusCode(status);
        response.setHeaders(Map.of());
        response.setBody("");
        response.setIsBase64Encoded(false);
        return response;
    }

    private static boolean acceptsJson(APIGatewayV2HTTPEvent event) {
        String accept = header(event, "accept");
        if (accept == null) {
            return true;
        }
        for (String mediaRange : accept.split(",")) {
            String[] parts = mediaRange.split(";");
            String mediaType = parts[0].trim().toLowerCase(Locale.ROOT);
            double quality = 1.0;
            for (int index = 1; index < parts.length; index++) {
                String[] parameter = parts[index].trim().split("=", 2);
                if (parameter.length == 2 && "q".equalsIgnoreCase(parameter[0].trim())) {
                    try {
                        quality = Double.parseDouble(parameter[1].trim());
                    } catch (NumberFormatException exception) {
                        quality = 0.0;
                    }
                    break;
                }
            }
            if (quality <= 0.0) {
                continue;
            }
            int slash = mediaType.indexOf('/');
            if (slash <= 0 || slash != mediaType.lastIndexOf('/')) {
                continue;
            }
            String type = mediaType.substring(0, slash);
            String subtype = mediaType.substring(slash + 1);
            if (("*".equals(type) || "application".equals(type))
                    && ("*".equals(subtype)
                    || "json".equals(subtype)
                    || subtype.endsWith("+json"))) {
                return true;
            }
        }
        return false;
    }

    private static boolean hasJsonContentType(APIGatewayV2HTTPEvent event) {
        if (event == null || event.getHeaders() == null) {
            return false;
        }
        String contentType = header(event, "content-type");
        if (contentType == null) {
            return false;
        }
        String mediaType = contentType.split(";", 2)[0].trim().toLowerCase(Locale.ROOT);
        return "application/json".equals(mediaType)
                || (mediaType.startsWith("application/") && mediaType.endsWith("+json"));
    }

    private static String header(APIGatewayV2HTTPEvent event, String name) {
        if (event == null || event.getHeaders() == null) {
            return null;
        }
        return event.getHeaders().entrySet().stream()
                .filter(entry -> name.equalsIgnoreCase(entry.getKey()))
                .map(Map.Entry::getValue)
                .findFirst()
                .orElse(null);
    }

    private static boolean isValid(SubmitFeedbackRequest request) {
        return !isBlank(request.getUserId())
                && request.getUserId().length() <= 100
                && request.getRating() >= 1
                && request.getRating() <= 5
                && !isBlank(request.getMessage())
                && request.getMessage().length() <= 2_000;
    }

    private static boolean isBlank(String value) {
        return value == null || value.trim().isEmpty();
    }

    private static List<String> allowedMethods(String path) {
        if (BASE_PATH.equals(path)) {
            return List.of("GET", "POST");
        }
        if (AVERAGE_PATH.equals(path)) {
            return List.of("GET");
        }
        return null;
    }

    private static String requestPath(APIGatewayV2HTTPEvent event) {
        if (event == null) {
            return "/";
        }
        return event.getRawPath() == null ? "/" : event.getRawPath();
    }

    private static String requestMethod(APIGatewayV2HTTPEvent event) {
        if (event == null
                || event.getRequestContext() == null
                || event.getRequestContext().getHttp() == null
                || event.getRequestContext().getHttp().getMethod() == null) {
            return "";
        }
        return event.getRequestContext().getHttp().getMethod().toUpperCase(Locale.ROOT);
    }

    private static String normalizePath(String path) {
        if (path.length() > 1 && path.endsWith("/")) {
            return path.substring(0, path.length() - 1);
        }
        return path;
    }

    private static ObjectMapper createMapper() {
        ObjectMapper mapper = new ObjectMapper();
        mapper.configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);
        mapper.configure(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS, false);
        mapper.registerModule(new JavaTimeModule());
        return mapper;
    }

    @JsonPropertyOrder({"id", "userId", "rating", "message", "createdAt"})
    private static final class FeedbackResponse {

        private final Long id;
        private final String userId;
        private final int rating;
        private final String message;
        private final Instant createdAt;

        private FeedbackResponse(Long id, String userId, int rating, String message, Instant createdAt) {
            this.id = id;
            this.userId = userId;
            this.rating = rating;
            this.message = message;
            this.createdAt = createdAt;
        }

        private static FeedbackResponse from(Feedback feedback) {
            return new FeedbackResponse(feedback.id(), feedback.userId(), feedback.rating(),
                    feedback.message(), feedback.createdAt());
        }

        public Long getId() {
            return id;
        }

        public String getUserId() {
            return userId;
        }

        public int getRating() {
            return rating;
        }

        public String getMessage() {
            return message;
        }

        public Instant getCreatedAt() {
            return createdAt;
        }
    }

    @JsonPropertyOrder({"averageRating"})
    private static final class AverageRatingResponse {

        private final double averageRating;

        private AverageRatingResponse(double averageRating) {
            this.averageRating = averageRating;
        }

        public double getAverageRating() {
            return averageRating;
        }
    }

    private static final class UnreadableBodyException extends RuntimeException {
    }

    private static final class InvalidRequestException extends RuntimeException {
    }
}
