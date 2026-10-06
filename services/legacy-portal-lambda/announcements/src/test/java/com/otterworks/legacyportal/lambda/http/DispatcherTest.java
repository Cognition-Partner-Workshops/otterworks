package com.otterworks.legacyportal.lambda.http;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicLong;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.otterworks.legacyportal.lambda.announcements.Announcement;
import com.otterworks.legacyportal.lambda.announcements.AnnouncementRepository;
import com.otterworks.legacyportal.lambda.announcements.AnnouncementService;
import com.otterworks.legacyportal.lambda.announcements.AnnouncementEvents;
import com.otterworks.legacyportal.lambda.http.Dispatcher.Request;
import com.otterworks.legacyportal.lambda.http.Dispatcher.Response;

class DispatcherTest {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private FakeRepository repo;
    private List<Announcement> published;
    private Dispatcher dispatcher;

    static class FakeRepository implements AnnouncementRepository {
        final List<Announcement> rows = new ArrayList<>();
        final AtomicLong ids = new AtomicLong(1);

        @Override
        public Announcement save(Announcement a) {
            if (a.getId() == null) {
                a.setId(ids.getAndIncrement());
                rows.add(a);
                return a;
            }
            for (int i = 0; i < rows.size(); i++) {
                if (rows.get(i).getId().equals(a.getId())) {
                    rows.set(i, a);
                    return a;
                }
            }
            rows.add(a);
            return a;
        }

        @Override
        public List<Announcement> findByPublishedTrueOrderByCreatedAtDesc() {
            List<Announcement> out = new ArrayList<>();
            for (Announcement a : rows) {
                if (a.isPublished()) {
                    out.add(a);
                }
            }
            out.sort((x, y) -> y.getCreatedAt().compareTo(x.getCreatedAt()));
            return out;
        }

        @Override
        public List<Announcement> findAll() {
            return new ArrayList<>(rows);
        }

        @Override
        public Optional<Announcement> findById(Long id) {
            return rows.stream().filter(a -> a.getId().equals(id)).findFirst();
        }
    }

    @BeforeEach
    void setUp() {
        repo = new FakeRepository();
        published = new ArrayList<>();
        AnnouncementEvents events = published::add;
        dispatcher = new Dispatcher(new AnnouncementService(repo, events));
    }

    private static Map<String, String> headers(String... kv) {
        Map<String, String> h = new HashMap<>();
        for (int i = 0; i + 1 < kv.length; i += 2) {
            h.put(kv[i], kv[i + 1]);
        }
        return h;
    }

    private Response call(String method, String path, Map<String, String> headers, String body) {
        return dispatcher.dispatch(new Request(method, path, "",
                headers, body == null ? new byte[0] : body.getBytes(StandardCharsets.UTF_8)));
    }

    private Response get(String path) {
        return call("GET", path, headers(), null);
    }

    private Response get(String path, String rawQuery) {
        return dispatcher.dispatch(new Request("GET", path, rawQuery, headers(), new byte[0]));
    }

    private Response post(String path, String contentType, String body) {
        Map<String, String> h = headers();
        if (contentType != null) {
            h.put("content-type", contentType);
        }
        return call("POST", path, h, body);
    }

    private static JsonNode json(Response r) throws Exception {
        return MAPPER.readTree(r.body());
    }

    @Test
    void wrongCaseAnnouncementsPathIs404() throws Exception {
        Response r = get("/API/announcements");
        assertEquals(404, r.status());
        JsonNode b = json(r);
        assertEquals("Not Found", b.get("error").asText());
        assertEquals("/API/announcements", b.get("path").asText());
        assertTrue(b.get("timestamp").asText()
                .matches("^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}\\.\\d{3}\\+00:00$"));
    }

    @Test
    void nonJsonAcceptIs406() {
        Response r = call("GET", "/api/announcements", headers("accept", "application/xml"), null);
        assertEquals(406, r.status());
        assertEquals("", r.body());
        assertTrue(r.headers().isEmpty());
    }

    @Test
    void wildcardAcceptStillJson() {
        Map<String, String> h = headers("accept",
                "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8");
        Response r = call("GET", "/api/announcements", h, null);
        assertEquals(200, r.status());
        assertEquals("application/json", r.headers().get("Content-Type"));
    }

    // ---- AnnouncementCreated events ----

    @Test
    void createPublishesOneEventPerAnnouncement() throws Exception {
        Response c = post("/api/announcements", "application/json",
                "{\"title\": \"Release\", \"body\": \"v1 is out\", \"published\": true}");
        assertEquals(201, c.status());
        assertEquals(1, published.size());
        assertEquals(json(c).get("id").asLong(), published.get(0).getId());
    }

    @Test
    void rejectedCreatesAndOtherWritesPublishNothing() {
        post("/api/announcements", "application/json", "{\"body\": \"no title\"}");
        post("/api/announcements", "application/json", "{\"title\":");
        post("/api/announcements", "text/plain", "title=x");
        call("PUT", "/api/announcements", headers("content-type", "application/json"), "{\"title\": \"x\", \"body\": \"y\"}");
        assertTrue(published.isEmpty());

        post("/api/announcements", "application/json", "{\"title\": \"Draft\", \"body\": \"coming soon\"}");
        dispatcher.dispatch(new Request("POST", "/api/announcements/1/publish", "", headers(), new byte[0]));
        assertEquals(1, published.size());
    }

    // ---- announcements routing ----

    @Test
    void emptyList() throws Exception {
        Response r = get("/api/announcements");
        assertEquals(200, r.status());
        assertEquals("[]", r.body());
    }

    @Test
    void trailingSlashList() {
        assertEquals(200, get("/api/announcements/").status());
    }

    @Test
    void createAndReadBack() throws Exception {
        Response c = post("/api/announcements", "application/json",
                "{\"title\": \"Release\", \"body\": \"v1 is out\", \"published\": true}");
        assertEquals(201, c.status());
        JsonNode created = json(c);
        assertEquals(1, created.get("id").asLong());
        assertEquals("Release", created.get("title").asText());
        assertTrue(created.get("published").asBoolean());
        assertTrue(created.get("createdAt").asText()
                .matches("^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(\\.(\\d{3}|\\d{6}|\\d{9}))?Z$"));

        JsonNode one = json(get("/api/announcements/1"));
        assertEquals("v1 is out", one.get("body").asText());
        assertEquals(404, get("/api/announcements/999").status());
    }

    @Test
    void getMissingIs404WithHandlerBody() throws Exception {
        Response r = get("/api/announcements/999");
        JsonNode b = json(r);
        assertEquals("Not Found", b.get("error").asText());
        assertEquals("announcement 999 not found", b.get("message").asText());
    }

    @Test
    void badIdIs400WithMessage() throws Exception {
        JsonNode b = json(get("/api/announcements/abc"));
        assertEquals("Bad Request", b.get("error").asText());
        assertEquals("For input string: \"abc\"", b.get("message").asText());
        JsonNode big = json(get("/api/announcements/99999999999999999999"));
        assertEquals("For input string: \"99999999999999999999\"", big.get("message").asText());
    }

    @Test
    void publishedOnlyParsing() throws Exception {
        Response bad = get("/api/announcements", "publishedOnly=abc");
        assertEquals(400, bad.status());
        JsonNode b = json(bad);
        assertEquals("Bad Request", b.get("error").asText());
        assertEquals("Invalid boolean value [abc]", b.get("message").asText());
        assertEquals(200, get("/api/announcements", "publishedOnly=FALSE").status());
        assertEquals(200, get("/api/announcements", "publishedOnly=").status());
        assertEquals(200, get("/api/announcements", "publishedOnly=0").status());
    }

    @Test
    void methodNotAllowed() throws Exception {
        assertEquals(405, call("DELETE", "/api/announcements/1", headers(), null).status());
        assertEquals(405, call("PUT", "/api/announcements", headers(), null).status());
        Response r = call("PUT", "/api/announcements", headers(), null);
        JsonNode b = json(r);
        assertEquals("Method Not Allowed", b.get("error").asText());
        assertEquals("/api/announcements", b.get("path").asText());
    }

    @Test
    void unsupportedMediaType() throws Exception {
        Response r = post("/api/announcements", "text/plain", "title=x");
        assertEquals(415, r.status());
        JsonNode b = json(r);
        assertEquals("Unsupported Media Type", b.get("error").asText());
    }

    @Test
    void missingAndMalformedBody() throws Exception {
        assertEquals(400, post("/api/announcements", "application/json", "").status());
        assertEquals(400, post("/api/announcements", "application/json", "{\"title\":").status());
        JsonNode b = json(post("/api/announcements", "application/json", ""));
        assertEquals("Bad Request", b.get("error").asText());
        assertEquals("/api/announcements", b.get("path").asText());
    }

    @Test
    void validationFailures() throws Exception {
        assertEquals(400, post("/api/announcements", "application/json", "{\"body\": \"no title\"}").status());
        assertEquals(400, post("/api/announcements", "application/json",
                "{\"title\": \"   \", \"body\": \"blank title\"}").status());
        assertEquals(400, post("/api/announcements", "application/json",
                "{\"title\": \"" + "x".repeat(201) + "\", \"body\": \"y\"}").status());
        assertEquals(400, post("/api/announcements", "application/json",
                "{\"title\": \"ok\", \"body\": \"" + "y".repeat(4001) + "\"}").status());
        // case-sensitive property names: Title is unknown, title stays null
        assertEquals(400, post("/api/announcements", "application/json",
                "{\"Title\": \"Case\", \"body\": \"x\"}").status());
    }

    @Test
    void coercionUnknownFieldsAndTrailingTokens() throws Exception {
        Response c1 = post("/api/announcements", "application/json",
                "{\"title\":\"Coerced\",\"body\":\"string bool\",\"published\":\"true\"}");
        assertEquals(201, c1.status());
        assertTrue(json(c1).get("published").asBoolean());

        Response c2 = post("/api/announcements", "application/json",
                "{\"title\": \"Extra\", \"body\": \"u\", \"published\": false, \"author\": \"nobody\"}");
        assertEquals(201, c2.status());

        Response c3 = post("/api/announcements", "application/json",
                "{\"title\": \"Trailing\", \"body\": \"tokens\"} xyz");
        assertEquals(201, c3.status());
    }

    @Test
    void latin1CharsetDecode() throws Exception {
        byte[] raw = "{\"title\": \"café\", \"body\": \"latin-1 body\", \"published\": true}"
                .getBytes("ISO-8859-1");
        Response r = dispatcher.dispatch(new Request("POST", "/api/announcements", "",
                headers("content-type", "application/json;charset=ISO-8859-1"), raw));
        assertEquals(201, r.status());
        assertEquals("café", json(r).get("title").asText());
    }

    @Test
    void publishFlow() throws Exception {
        post("/api/announcements", "application/json", "{\"title\": \"Draft\", \"body\": \"coming soon\"}");
        Response p = dispatcher.dispatch(new Request("POST", "/api/announcements/1/publish", "",
                headers(), new byte[0]));
        assertEquals(200, p.status());
        assertTrue(json(p).get("published").asBoolean());
        assertEquals(404, dispatcher.dispatch(new Request("POST", "/api/announcements/999/publish", "",
                headers(), new byte[0])).status());
        // published ordering: published-only list sorts desc by createdAt
        post("/api/announcements", "application/json", "{\"title\": \"B\", \"body\": \"b\", \"published\": true}");
        JsonNode list = json(get("/api/announcements"));
        assertEquals(2, list.size());
        assertEquals("B", list.get(0).get("title").asText());
        JsonNode all = json(get("/api/announcements", "publishedOnly=false"));
        assertEquals(2, all.size());
    }
}
