package com.otterworks.legacyportal.lambda.feedback;

import com.amazonaws.services.lambda.runtime.RequestHandler;
import com.amazonaws.services.lambda.runtime.events.APIGatewayV2HTTPEvent;
import com.amazonaws.services.lambda.runtime.events.APIGatewayV2HTTPResponse;
import com.fasterxml.jackson.annotation.JsonPropertyOrder;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

public final class FeedbackHandler
        implements RequestHandler<APIGatewayV2HTTPEvent, APIGatewayV2HTTPResponse> {
    private static final String ROOT_PATH = "/api/feedback";
    private static final String AVERAGE_PATH = "/api/feedback/average-rating";
    private static final ObjectMapper MAPPER = new ObjectMapper()
            .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);
    private static final DateTimeFormatter ERROR_TIMESTAMP =
            DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss.SSS'+00:00'")
                    .withZone(ZoneOffset.UTC);

    private final FeedbackService service;
    private final boolean failReads;

    public FeedbackHandler() {
        this(new DataApiFeedbackRepository(), "1".equals(System.getenv("FAIL_READS")));
    }

    public FeedbackHandler(FeedbackRepository repository) {
        this(repository, false);
    }

    public FeedbackHandler(FeedbackRepository repository, boolean failReads) {
        this.service = new FeedbackService(repository);
        this.failReads = failReads;
    }

    @Override
    public APIGatewayV2HTTPResponse handleRequest(
            APIGatewayV2HTTPEvent event, com.amazonaws.services.lambda.runtime.Context context) {
        String path = event == null || event.getRawPath() == null ? "" : event.getRawPath();
        String method = requestMethod(event);
        // FAIL_READS=1 is the canary demo's bad build: the same code, with every GET answering 500.
        if (failReads && "GET".equals(method)) {
            return error(500, path);
        }
        Route route = route(path);
        if (route == null) {
            return error(404, path);
        }

        if (!route.methods().contains(method)) {
            APIGatewayV2HTTPResponse response = error(405, path);
            response.getHeaders().put("Allow", route.allowedMethods());
            return response;
        }

        try {
            Object result;
            int successStatus;
            if (route == Route.ROOT && "POST".equals(method)) {
                if (!isJsonContentType(header(event, "content-type"))) {
                    return error(415, path);
                }
                SubmitRequest request;
                try {
                    request = parseRequest(event);
                } catch (JsonProcessingException | IllegalArgumentException invalidBody) {
                    return error(400, path);
                }
                if (request == null || !valid(request)) {
                    return error(400, path);
                }
                result = FeedbackResponse.from(service.submit(request.userId, request.rating, request.message));
                successStatus = 201;
            } else if (route == Route.ROOT) {
                String userId;
                try {
                    userId = queryParameter(event == null ? null : event.getRawQueryString(), "userId");
                } catch (IllegalArgumentException invalidQuery) {
                    return error(400, path);
                }
                if (userId == null) {
                    return error(400, path);
                }
                result = service.listForUser(userId).stream().map(FeedbackResponse::from).toList();
                successStatus = 200;
            } else {
                result = new AverageRatingResponse(service.averageRating());
                successStatus = 200;
            }

            if (!acceptsJson(header(event, "accept"))) {
                return response(406, "", Collections.emptyMap());
            }
            return jsonResponse(successStatus, result);
        } catch (Exception exception) {
            exception.printStackTrace(System.err);
            return error(500, path);
        }
    }

    private static SubmitRequest parseRequest(APIGatewayV2HTTPEvent event)
            throws JsonProcessingException {
        String body = event == null ? null : event.getBody();
        if (event != null && Boolean.TRUE.equals(event.getIsBase64Encoded())) {
            if (body == null) {
                return null;
            }
            try {
                body = new String(Base64.getDecoder().decode(body), StandardCharsets.UTF_8);
            } catch (IllegalArgumentException invalidBase64) {
                return null;
            }
        }
        if (body == null || body.isEmpty()) {
            return null;
        }
        return MAPPER.readValue(body, SubmitRequest.class);
    }

    private static boolean valid(SubmitRequest request) {
        return notBlank(request.userId)
                && request.userId.length() <= 100
                && request.rating >= 1
                && request.rating <= 5
                && notBlank(request.message)
                && request.message.length() <= 2000;
    }

    private static boolean notBlank(String value) {
        if (value == null) {
            return false;
        }
        for (int i = 0; i < value.length(); i++) {
            if (!Character.isWhitespace(value.charAt(i))) {
                return true;
            }
        }
        return false;
    }

    private static Route route(String path) {
        if (ROOT_PATH.equals(path) || (ROOT_PATH + "/").equals(path)) {
            return Route.ROOT;
        }
        if (AVERAGE_PATH.equals(path)) {
            return Route.AVERAGE;
        }
        return null;
    }

    private static String requestMethod(APIGatewayV2HTTPEvent event) {
        if (event == null || event.getRequestContext() == null || event.getRequestContext().getHttp() == null) {
            return "";
        }
        String method = event.getRequestContext().getHttp().getMethod();
        return method == null ? "" : method;
    }

    private static String header(APIGatewayV2HTTPEvent event, String name) {
        if (event == null || event.getHeaders() == null) {
            return null;
        }
        for (Map.Entry<String, String> entry : event.getHeaders().entrySet()) {
            if (entry.getKey() != null && entry.getKey().equalsIgnoreCase(name)) {
                return entry.getValue();
            }
        }
        return null;
    }

    private static String queryParameter(String rawQuery, String name) {
        if (rawQuery == null || rawQuery.isEmpty()) {
            return null;
        }
        for (String pair : rawQuery.split("&", -1)) {
            int separator = pair.indexOf('=');
            String key = separator < 0 ? pair : pair.substring(0, separator);
            String value = separator < 0 ? "" : pair.substring(separator + 1);
            if (URLDecoder.decode(key, StandardCharsets.UTF_8).equals(name)) {
                return URLDecoder.decode(value, StandardCharsets.UTF_8);
            }
        }
        return null;
    }

    private static boolean isJsonContentType(String contentType) {
        if (contentType == null) {
            return false;
        }
        String[] parts = contentType.split(";", 2);
        String mediaType = parts[0].trim().toLowerCase(Locale.ROOT);
        if (!mediaType.startsWith("application/")) {
            return false;
        }
        String subtype = mediaType.substring("application/".length());
        return subtype.equals("json") || (subtype.endsWith("+json") && subtype.length() > 5);
    }

    private static boolean acceptsJson(String accept) {
        if (accept == null || accept.isBlank()) {
            return true;
        }
        List<MediaRange> ranges = new ArrayList<>();
        for (String rawRange : accept.split(",")) {
            String[] parts = rawRange.trim().split(";");
            String[] type = parts[0].trim().toLowerCase(Locale.ROOT).split("/", -1);
            if (type.length != 2) {
                continue;
            }
            double quality = 1.0;
            for (int i = 1; i < parts.length; i++) {
                String[] parameter = parts[i].trim().split("=", 2);
                if (parameter.length == 2 && parameter[0].trim().equalsIgnoreCase("q")) {
                    try {
                        quality = Double.parseDouble(parameter[1].trim());
                    } catch (NumberFormatException invalidQuality) {
                        quality = 0.0;
                    }
                }
            }
            if (!Double.isFinite(quality) || quality < 0.0 || quality > 1.0) {
                quality = 0.0;
            }
            ranges.add(new MediaRange(type[0], type[1], quality));
        }

        int specificity = -1;
        double bestQuality = 0.0;
        for (MediaRange range : ranges) {
            int currentSpecificity = range.specificityForJson();
            if (currentSpecificity < 0) {
                continue;
            }
            if (currentSpecificity > specificity) {
                specificity = currentSpecificity;
                bestQuality = range.quality();
            } else if (currentSpecificity == specificity) {
                bestQuality = Math.max(bestQuality, range.quality());
            }
        }
        return specificity >= 0 && bestQuality > 0.0;
    }

    private static APIGatewayV2HTTPResponse jsonResponse(int status, Object body) throws JsonProcessingException {
        return response(status, MAPPER.writeValueAsString(body), Map.of("Content-Type", "application/json"));
    }

    private static APIGatewayV2HTTPResponse error(int status, String path) {
        try {
            String body = MAPPER.writeValueAsString(new ErrorResponse(
                    ERROR_TIMESTAMP.format(Instant.now()), status, reason(status), path));
            return response(status, body, Map.of("Content-Type", "application/json"));
        } catch (JsonProcessingException impossible) {
            throw new IllegalStateException(impossible);
        }
    }

    private static String reason(int status) {
        return switch (status) {
            case 400 -> "Bad Request";
            case 404 -> "Not Found";
            case 405 -> "Method Not Allowed";
            case 415 -> "Unsupported Media Type";
            default -> "Internal Server Error";
        };
    }

    private static APIGatewayV2HTTPResponse response(int status, String body, Map<String, String> headers) {
        return APIGatewayV2HTTPResponse.builder()
                .withStatusCode(status)
                .withHeaders(new HashMap<>(headers))
                .withBody(body)
                .withIsBase64Encoded(false)
                .build();
    }

    private enum Route {
        ROOT(Set.of("GET", "POST"), "GET, POST"),
        AVERAGE(Set.of("GET"), "GET");

        private final Set<String> methods;
        private final String allowedMethods;

        Route(Set<String> methods, String allowedMethods) {
            this.methods = methods;
            this.allowedMethods = allowedMethods;
        }

        private Set<String> methods() {
            return methods;
        }

        private String allowedMethods() {
            return allowedMethods;
        }
    }

    private record MediaRange(String type, String subtype, double quality) {
        private int specificityForJson() {
            if (type.equals("application") && subtype.equals("json")) {
                return 2;
            }
            if (type.equals("application") && subtype.equals("*")) {
                return 1;
            }
            if (type.equals("*") && subtype.equals("*")) {
                return 0;
            }
            return -1;
        }
    }

    public static final class SubmitRequest {
        public String userId;
        public int rating;
        public String message;
    }

    @JsonPropertyOrder({"id", "userId", "rating", "message", "createdAt"})
    private record FeedbackResponse(Long id, String userId, int rating, String message, String createdAt) {
        private static FeedbackResponse from(Feedback feedback) {
            return new FeedbackResponse(
                    feedback.id(),
                    feedback.userId(),
                    feedback.rating(),
                    feedback.message(),
                    feedback.createdAt().toString());
        }
    }

    @JsonPropertyOrder({"averageRating"})
    private record AverageRatingResponse(double averageRating) {
    }

    @JsonPropertyOrder({"timestamp", "status", "error", "path"})
    private record ErrorResponse(String timestamp, int status, String error, String path) {
    }
}
