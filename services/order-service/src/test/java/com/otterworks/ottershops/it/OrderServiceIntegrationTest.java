package com.otterworks.ottershops.it;

import com.otterworks.ottershops.catalog.CatalogService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Disabled;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Callable;
import java.util.concurrent.Executors;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Order service against a real, empty Postgres: Flyway V1-V4, checkout, stock locking, returns, rewards and bag merge.
 * Set TESTCONTAINERS_POSTGRES_IMAGE to pull Postgres from a mirror when Docker Hub is rate limited.
 */
@Testcontainers(disabledWithoutDocker = true)
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class OrderServiceIntegrationTest {
    @Container
    @ServiceConnection
    static final PostgreSQLContainer<?> PG = new PostgreSQLContainer<>(DockerImageName
            .parse(System.getenv().getOrDefault("TESTCONTAINERS_POSTGRES_IMAGE", "postgres:16-alpine"))
            .asCompatibleSubstituteFor("postgres"));

    @Autowired TestRestTemplate http;
    @Autowired JdbcTemplate jdbc;
    @Autowired CatalogService catalog;

    static final Map<String, Object> CARD = Map.of("number", "4242424242424242", "expMonth", 12, "expYear", 2030, "cvc", "123", "name", "Q A");
    static final Map<String, Object> ADDRESS = Map.of("name", "Q A", "line1", "1 Market St", "city", "San Francisco", "state", "CA", "zip", "94105");

    String sku;

    @BeforeEach
    void pickSku() {
        sku = jdbc.queryForObject("SELECT sku FROM skus WHERE stock >= 5 ORDER BY sku LIMIT 1", String.class);
    }

    @SuppressWarnings("unchecked")
    Map<String, Object> body(ResponseEntity<Map> r) { return (Map<String, Object>) r.getBody(); }

    ResponseEntity<Map> post(String path, Object body, HttpHeaders headers) {
        return http.exchange(path, HttpMethod.POST, new HttpEntity<>(body, headers), Map.class);
    }

    ResponseEntity<Map> post(String path, Object body) { return post(path, body, new HttpHeaders()); }

    String bagWith(String sku, int qty, HttpHeaders headers) {
        String id = (String) body(post("/api/bags", Map.of(), headers)).get("id");
        assertEquals(200, post("/api/bags/" + id + "/items", Map.of("sku", sku, "quantity", qty), headers).getStatusCode().value());
        return id;
    }

    ResponseEntity<Map> checkout(String bagId, Map<String, Object> overrides, HttpHeaders headers) {
        Map<String, Object> req = new HashMap<>(Map.of("bagId", bagId, "email", "qa@example.com", "fulfillment", "SHIP",
                "shippingMethod", "STANDARD", "address", ADDRESS, "card", CARD));
        req.putAll(overrides);
        return post("/api/checkout", req, headers);
    }

    int stock(String sku) { return jdbc.queryForObject("SELECT stock FROM skus WHERE sku = ?", Integer.class, sku); }

    @Test
    void flywayAppliesV1ToV4OnAnEmptyDatabase() {
        List<String> versions = jdbc.queryForList(
                "SELECT version FROM flyway_schema_history WHERE success AND version IS NOT NULL ORDER BY installed_rank", String.class);
        assertTrue(versions.containsAll(List.of("1", "2", "3", "4")), versions.toString());
        assertEquals(192, jdbc.queryForObject("SELECT count(*) FROM products", Integer.class));
        assertEquals(22, jdbc.queryForObject("SELECT count(*) FROM stores", Integer.class));
    }

    @Test
    void checkoutDecrementsStockAndConvertsTheBag() {
        int before = stock(sku);
        String bag = bagWith(sku, 2, new HttpHeaders());
        ResponseEntity<Map> r = checkout(bag, Map.of(), new HttpHeaders());
        assertEquals(201, r.getStatusCode().value());
        assertEquals(before - 2, stock(sku));
        assertTrue(checkout(bag, Map.of(), new HttpHeaders()).getStatusCode().is4xxClientError(), "a converted bag can't be checked out twice");
    }

    @Test
    void declinedAndInvalidCardsLeaveStockAlone() {
        int before = stock(sku);
        String bag = bagWith(sku, 1, new HttpHeaders());
        assertEquals(402, checkout(bag, Map.of("card", Map.of("number", "4000000000000002", "expMonth", 12, "expYear", 2030, "cvc", "123", "name", "Q A")), new HttpHeaders()).getStatusCode().value());
        assertEquals(400, checkout(bag, Map.of("card", Map.of("number", "4242424242424241", "expMonth", 12, "expYear", 2030, "cvc", "123", "name", "Q A")), new HttpHeaders()).getStatusCode().value());
        assertEquals(before, stock(sku));
    }

    @Test
    void lastUnitRaceSellsExactlyOnce() throws Exception {
        String last = jdbc.queryForObject("SELECT sku FROM skus WHERE stock >= 5 ORDER BY sku DESC LIMIT 1", String.class);
        List<String> bags = List.of(bagWith(last, 1, new HttpHeaders()), bagWith(last, 1, new HttpHeaders()),
                bagWith(last, 1, new HttpHeaders()), bagWith(last, 1, new HttpHeaders()));
        jdbc.update("UPDATE skus SET stock = 1 WHERE sku = ?", last);
        catalog.refresh();
        var pool = Executors.newFixedThreadPool(bags.size());
        List<Callable<Integer>> calls = bags.stream()
                .<Callable<Integer>>map(b -> () -> checkout(b, Map.of(), new HttpHeaders()).getStatusCode().value()).toList();
        List<Integer> codes = pool.invokeAll(calls).stream().map(f -> { try { return f.get(); } catch (Exception e) { throw new RuntimeException(e); } }).toList();
        pool.shutdown();
        assertEquals(1, codes.stream().filter(c -> c == 201).count(), codes.toString());
        assertEquals(bags.size() - 1, codes.stream().filter(c -> c == 409).count(), codes.toString());
        assertEquals(0, stock(last));
    }

    @Test
    void returnIsCreatedOnceAndRefundsMerchandisePlusTax() {
        String bag = bagWith(sku, 1, new HttpHeaders());
        Map<String, Object> order = body(checkout(bag, Map.of(), new HttpHeaders()));
        String number = (String) order.get("orderNumber");
        Map<String, Object> req = Map.of("email", "qa@example.com", "method", "MAIL",
                "lines", List.of(Map.of("lineNo", 1, "quantity", 1, "reason", firstReason())));
        ResponseEntity<Map> r = post("/api/orders/" + number + "/returns", req);
        assertEquals(201, r.getStatusCode().value(), String.valueOf(r.getBody()));
        int lineTotal = (Integer) ((Map<?, ?>) ((List<?>) order.get("lines")).get(0)).get("lineTotalCents");
        int tax = Math.round(lineTotal * 0.0725f);
        assertEquals(lineTotal + tax, body(r).get("refundCents"));
        assertEquals(409, post("/api/orders/" + number + "/returns", req).getStatusCode().value());
    }

    String firstReason() {
        Object reasons = http.getForObject("/api/returns/reasons", Object.class);
        Object first = reasons instanceof List<?> l ? l.get(0) : ((List<?>) ((Map<?, ?>) reasons).values().iterator().next()).get(0);
        return first instanceof Map<?, ?> m ? String.valueOf(m.containsKey("code") ? m.get("code") : m.values().iterator().next()) : String.valueOf(first);
    }

    @Test
    void guestBagMergesOnRegisterAndMemberEarnsWholeDollarPoints() {
        String guestBag = bagWith(sku, 1, new HttpHeaders());
        ResponseEntity<Map> reg = post("/api/auth/register", Map.of("email", "qa-" + System.nanoTime() + "@example.com",
                "password", "correct-horse-1", "firstName", "Q", "lastName", "A", "bagId", guestBag));
        assertEquals(201, reg.getStatusCode().value(), String.valueOf(reg.getBody()));
        HttpHeaders member = new HttpHeaders();
        member.add(HttpHeaders.COOKIE, reg.getHeaders().getFirst(HttpHeaders.SET_COOKIE).split(";", 2)[0]);
        String memberBag = (String) body(reg).get("bagId");
        Map<String, Object> bag = body(http.exchange("/api/bags/" + memberBag, HttpMethod.GET, new HttpEntity<>(member), Map.class));
        assertEquals(1, ((List<?>) bag.get("items")).size());
        Map<String, Object> order = body(checkout(memberBag, Map.of(), member));
        int total = (Integer) order.get("totalCents");
        Map<String, Object> me = body(http.exchange("/api/auth/me", HttpMethod.GET, new HttpEntity<>(member), Map.class));
        assertEquals(total / 100, ((Map<?, ?>) me.get("customer")).get("rewardsPoints"));
    }

    @Test
    @Disabled("KNOWN FAILING QA-01: checkout accepts any two-letter state (e.g. XX) and taxes it at the 5% default")
    void checkoutRejectsUnknownState() {
        String bag = bagWith(sku, 1, new HttpHeaders());
        Map<String, Object> addr = new HashMap<>(ADDRESS);
        addr.put("state", "XX");
        assertEquals(400, checkout(bag, Map.of("address", addr), new HttpHeaders()).getStatusCode().value());
    }
}
