package com.otterworks.legacyportal.lambda.http;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.URLDecoder;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.NoSuchElementException;

import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.otterworks.legacyportal.lambda.announcements.Announcement;
import com.otterworks.legacyportal.lambda.announcements.AnnouncementService;

/**
 * Routes the announcements requests API Gateway hands to the function the way the Spring
 * Boot 2.7 monolith did: the same patterns Spring's PathMatcher matches (including the
 * trailing-slash match), the same method/content negotiation, the same error bodies.
 * Every other path stays on the EC2 monolith through the HTTP API's $default route.
 */
public class Dispatcher {

    public record Request(String method, String path, String rawQueryString,
                          Map<String, String> headers, byte[] body) {
    }

    public record Response(int status, Map<String, String> headers, String body) {
    }

    private static final String JSON = "application/json";
    private static final DateTimeFormatter ERROR_TS =
            DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss.SSSxxx");

    private final AnnouncementService service;
    private final ObjectMapper mapper;

    public Dispatcher(AnnouncementService service) {
        this.service = service;
        this.mapper = new ObjectMapper();
        this.mapper.configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);
    }

    public Response dispatch(Request req) {
        String method = req.method().toUpperCase(Locale.ROOT);
        String path = req.path();

        // Announcements context. Spring 2.7's trailing-slash match folds "/x/" onto "/x".
        String normalized = stripTrailingSlash(path);
        if (normalized.equals("/api/announcements")) {
            switch (method) {
                case "GET":
                    return negotiated(req, () -> list(req));
                case "POST":
                    return negotiated(req, () -> create(req));
                default:
                    return error(405, "Method Not Allowed", path);
            }
        }
        String id = matchId(normalized);
        if (id != null) {
            if (method.equals("GET")) {
                return negotiated(req, () -> {
                    try {
                        return announcementJson(200, service.get(parseId(id)));
                    } catch (NoSuchElementException | IllegalArgumentException e) {
                        return handled(e);
                    }
                });
            }
            return error(405, "Method Not Allowed", path);
        }
        String publishId = matchPublishId(normalized);
        if (publishId != null) {
            if (method.equals("POST")) {
                return negotiated(req, () -> {
                    try {
                        return announcementJson(200, service.publish(parseId(publishId)));
                    } catch (NoSuchElementException | IllegalArgumentException e) {
                        return handled(e);
                    }
                });
            }
            return error(405, "Method Not Allowed", path);
        }
        return error(404, "Not Found", path);
    }

    private static String stripTrailingSlash(String path) {
        return path.endsWith("/") && path.length() > 1 ? path.substring(0, path.length() - 1) : path;
    }

    private static String matchId(String path) {
        String prefix = "/api/announcements/";
        if (path.startsWith(prefix)) {
            String rest = path.substring(prefix.length());
            if (!rest.isEmpty() && !rest.contains("/")) {
                return rest;
            }
        }
        return null;
    }

    private static String matchPublishId(String path) {
        String prefix = "/api/announcements/";
        String suffix = "/publish";
        if (path.startsWith(prefix) && path.endsWith(suffix)) {
            String rest = path.substring(prefix.length(), path.length() - suffix.length());
            if (!rest.isEmpty() && !rest.contains("/")) {
                return rest;
            }
        }
        return null;
    }

    // ---- announcements endpoints ----

    private Response list(Request req) {
        boolean publishedOnly;
        try {
            publishedOnly = parsePublishedOnly(queryParam(req, "publishedOnly"));
        } catch (IllegalArgumentException e) {
            return handled(e);
        }
        List<Announcement> announcements =
                publishedOnly ? service.listPublished() : service.listAll();
        ArrayNode array = mapper.createArrayNode();
        for (Announcement a : announcements) {
            array.add(announcementNode(a));
        }
        return json(200, write(array));
    }

    private Response create(Request req) {
        String contentType = req.headers().get("content-type");
        if (!isJsonContentType(contentType)) {
            return error(415, "Unsupported Media Type", req.path());
        }
        byte[] raw = req.body() == null ? new byte[0] : req.body();
        if (raw.length == 0) {
            return error(400, "Bad Request", req.path());
        }
        CreateAnnouncementRequest request;
        try {
            String text = new String(raw, charsetOf(contentType));
            request = mapper.readValue(text, CreateAnnouncementRequest.class);
        } catch (IOException e) {
            return error(400, "Bad Request", req.path());
        }
        if (!valid(request)) {
            return error(400, "Bad Request", req.path());
        }
        Announcement saved = service.create(request.title, request.body, request.published);
        return announcementJson(201, saved);
    }

    private static boolean isJsonContentType(String contentType) {
        if (contentType == null) {
            return false;
        }
        String media = contentType.split(";", 2)[0].trim().toLowerCase(Locale.ROOT);
        return media.equals("application/json")
                || (media.startsWith("application/") && media.endsWith("+json"));
    }

    private static Charset charsetOf(String contentType) {
        if (contentType != null) {
            for (String part : contentType.split(";")) {
                String p = part.trim();
                if (p.toLowerCase(Locale.ROOT).startsWith("charset=")) {
                    String name = p.substring("charset=".length()).replace("\"", "").trim();
                    try {
                        return Charset.forName(name);
                    } catch (Exception ignored) {
                    }
                }
            }
        }
        return StandardCharsets.UTF_8;
    }

    private static boolean valid(CreateAnnouncementRequest r) {
        return notBlank(r.title, 200) && notBlank(r.body, 4000);
    }

    private static boolean notBlank(String s, int max) {
        return s != null && !s.trim().isEmpty() && s.length() <= max;
    }

    private static Long parseId(String id) {
        return Long.parseLong(id);
    }

    // StringToBooleanConverter semantics: true/on/yes/1, false/off/no/0, case-insensitive;
    // the request-parameter default kicks in when the value is absent.
    private static boolean parsePublishedOnly(String value) {
        if (value == null || value.isEmpty()) {
            return true;
        }
        String v = value.trim().toLowerCase(Locale.ROOT);
        switch (v) {
            case "true": case "on": case "yes": case "1":
                return true;
            case "false": case "off": case "no": case "0":
                return false;
            default:
                throw new IllegalArgumentException("Invalid boolean value [" + value + "]");
        }
    }

    private static String queryParam(Request req, String name) {
        String raw = req.rawQueryString();
        if (raw == null || raw.isEmpty()) {
            return null;
        }
        for (String pair : raw.split("&")) {
            int eq = pair.indexOf('=');
            String k = eq >= 0 ? pair.substring(0, eq) : pair;
            if (urlDecode(k).equals(name)) {
                return eq >= 0 ? urlDecode(pair.substring(eq + 1)) : "";
            }
        }
        return null;
    }

    private static String urlDecode(String s) {
        return URLDecoder.decode(s, StandardCharsets.UTF_8);
    }

    // ---- response shapes ----

    private ObjectNode announcementNode(Announcement a) {
        ObjectNode b = mapper.createObjectNode();
        b.put("id", a.getId());
        b.put("title", a.getTitle());
        b.put("body", a.getBody());
        b.put("published", a.isPublished());
        b.put("createdAt", a.getCreatedAt() == null ? null : a.getCreatedAt().toString());
        return b;
    }

    private Response announcementJson(int status, Announcement a) {
        return json(status, write(announcementNode(a)));
    }

    // GlobalExceptionHandler: NoSuchElementException -> 404, IllegalArgumentException -> 400,
    // body {"error": <reason>, "message": <ex message>}.
    private Response handled(RuntimeException e) {
        int status = e instanceof NoSuchElementException ? 404 : 400;
        String reason = status == 404 ? "Not Found" : "Bad Request";
        ObjectNode b = mapper.createObjectNode();
        b.put("error", reason);
        b.put("message", e.getMessage());
        return json(status, write(b));
    }

    // BasicErrorController body: timestamp, status, error, path.
    private Response error(int status, String reason, String path) {
        ObjectNode b = mapper.createObjectNode();
        b.put("timestamp", ERROR_TS.format(OffsetDateTime.now(ZoneOffset.UTC)));
        b.put("status", status);
        b.put("error", reason);
        b.put("path", path);
        return json(status, write(b));
    }

    private static Response json(int status, String body) {
        Map<String, String> headers = new LinkedHashMap<>();
        headers.put("Content-Type", JSON);
        return new Response(status, headers, body);
    }

    // Negotiation for bodies written by @RestController methods: any range with q>0
    // compatible with application/json wins, else 406.
    private Response negotiated(Request req, java.util.function.Supplier<Response> produce) {
        if (!acceptsJson(req.headers().get("accept"))) {
            return new Response(406, new LinkedHashMap<>(), "");
        }
        return produce.get();
    }

    private static boolean acceptsJson(String accept) {
        if (accept == null || accept.trim().isEmpty()) {
            return true;
        }
        for (String range : accept.split(",")) {
            String media = range.split(";", 2)[0].trim().toLowerCase(Locale.ROOT);
            if (media.isEmpty()) {
                continue;
            }
            if (qZero(range)) {
                continue;
            }
            if (media.equals("*/*") || media.equals("application/*")
                    || media.equals("application/json") || media.endsWith("+json")) {
                return true;
            }
        }
        return false;
    }

    private static boolean qZero(String range) {
        for (String part : range.split(";")) {
            String p = part.trim();
            if (p.startsWith("q=")) {
                try {
                    return Double.parseDouble(p.substring(2)) <= 0;
                } catch (NumberFormatException e) {
                    return false;
                }
            }
        }
        return false;
    }

    private String write(JsonNode node) {
        try {
            return mapper.writeValueAsString(node);
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }

    // The shape of CreateAnnouncementRequest as Jackson binds it.
    public static class CreateAnnouncementRequest {
        public String title;
        public String body;
        public boolean published;
    }
}
