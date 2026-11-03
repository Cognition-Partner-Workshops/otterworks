package com.otterworks.ottershops.order;

import com.otterworks.ottershops.catalog.CatalogService;
import com.otterworks.ottershops.common.ApiException;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Clock;
import java.time.Duration;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

@Service
public class ReturnService {
    public static final Duration WINDOW = Duration.ofDays(45);
    public static final Set<String> REASONS = Set.of("Too small", "Too large", "Not as pictured", "Changed my mind",
            "Arrived damaged", "Ordered more than one size");
    static final Set<String> FINAL_SALE = Set.of("gift-cards");

    private final JdbcTemplate jdbc;
    private final CatalogService catalog;
    private final Clock clock;

    public ReturnService(JdbcTemplate jdbc, CatalogService catalog, Clock clock) {
        this.jdbc = jdbc;
        this.catalog = catalog;
        this.clock = clock;
    }

    public record LineRequest(Integer lineNo, Integer quantity, String reason) {}

    public record Request(String email, String method, List<LineRequest> lines) {}

    /** Refund for {@code qty} units of a line: its paid unit price plus the order's tax rate on it. */
    static int refund(OrderView.Line line, int qty, BigDecimal taxRate) {
        BigDecimal merch = BigDecimal.valueOf(line.lineTotalCents()).multiply(BigDecimal.valueOf(qty))
                .divide(BigDecimal.valueOf(line.quantity()), 0, RoundingMode.HALF_UP);
        BigDecimal tax = merch.multiply(taxRate).divide(BigDecimal.valueOf(100), 0, RoundingMode.HALF_UP);
        return merch.add(tax).intValueExact();
    }

    boolean finalSale(OrderView.Line line) {
        return catalog.findProduct(line.productId()).map(p -> p.collections().stream().anyMatch(FINAL_SALE::contains)).orElse(false);
    }

    Map<Integer, Integer> returned(UUID orderId) {
        Map<Integer, Integer> out = new HashMap<>();
        jdbc.query("""
                SELECT l.line_no, sum(l.quantity) FROM return_lines l JOIN returns r ON r.id = l.return_id
                WHERE r.order_id = ? GROUP BY l.line_no""", rs -> { out.put(rs.getInt(1), rs.getInt(2)); }, orderId);
        return out;
    }

    @Transactional
    public OrderView.ReturnView create(OrderView order, Request req) {
        if (order.createdAt().plus(WINDOW).isBefore(clock.instant())) {
            throw new ApiException(HttpStatus.CONFLICT, "RETURN_WINDOW_CLOSED", "Returns close 45 days after purchase");
        }
        String method = req.method() == null ? "MAIL" : req.method().toUpperCase();
        if (!method.equals("MAIL") && !method.equals("STORE")) throw ApiException.badRequest("METHOD_INVALID", "Choose mail or store return");
        if (req.lines() == null || req.lines().isEmpty()) throw ApiException.badRequest("RETURN_EMPTY", "Choose at least one item to return");
        jdbc.queryForObject("SELECT id FROM orders WHERE id = ? FOR UPDATE", UUID.class, order.id());
        Map<Integer, Integer> already = returned(order.id());
        Map<Integer, OrderView.Line> byNo = new HashMap<>();
        order.lines().forEach(l -> byNo.put(l.lineNo(), l));
        UUID id = UUID.randomUUID();
        String number = "R" + jdbc.queryForObject("SELECT nextval('return_number_seq')", Long.class);
        int total = 0;
        record Planned(int lineNo, int qty, String reason, int refund) {}
        List<Planned> planned = new java.util.ArrayList<>();
        Set<Integer> seen = new java.util.HashSet<>();
        for (LineRequest lr : req.lines()) {
            OrderView.Line line = lr.lineNo() == null ? null : byNo.get(lr.lineNo());
            if (line == null || !seen.add(line.lineNo())) throw ApiException.badRequest("LINE_INVALID", "Unknown item on this order");
            int qty = lr.quantity() == null ? 1 : lr.quantity();
            int left = line.quantity() - already.getOrDefault(line.lineNo(), 0);
            if (finalSale(line)) throw new ApiException(HttpStatus.CONFLICT, "FINAL_SALE", line.name() + " can't be returned");
            if (qty < 1 || qty > left) {
                throw new ApiException(HttpStatus.CONFLICT, "QUANTITY_INVALID",
                        left == 0 ? line.name() + " has already been returned" : "You can return up to " + left + " of " + line.name());
            }
            if (lr.reason() == null || !REASONS.contains(lr.reason())) throw ApiException.badRequest("REASON_INVALID", "Pick a reason for each item");
            int refund = refund(line, qty, order.taxRate());
            total += refund;
            planned.add(new Planned(line.lineNo(), qty, lr.reason(), refund));
        }
        jdbc.update("INSERT INTO returns (id, return_number, order_id, method, refund_cents) VALUES (?, ?, ?, ?, ?)",
                id, number, order.id(), method, total);
        for (Planned p : planned) {
            jdbc.update("INSERT INTO return_lines (return_id, line_no, quantity, reason, refund_cents) VALUES (?, ?, ?, ?, ?)",
                    id, p.lineNo(), p.qty(), p.reason(), p.refund());
        }
        jdbc.update("UPDATE orders SET updated_at = now() WHERE id = ?", order.id());
        return forOrder(order.id()).stream().filter(r -> r.returnNumber().equals(number)).findFirst().orElseThrow();
    }

    public List<OrderView.ReturnView> forOrder(UUID orderId) {
        Map<UUID, List<OrderView.ReturnLine>> lines = new HashMap<>();
        jdbc.query("""
                SELECT l.return_id, l.line_no, l.quantity, l.reason, l.refund_cents FROM return_lines l
                JOIN returns r ON r.id = l.return_id WHERE r.order_id = ? ORDER BY l.line_no""",
                rs -> { lines.computeIfAbsent(rs.getObject(1, UUID.class), k -> new java.util.ArrayList<>())
                        .add(new OrderView.ReturnLine(rs.getInt(2), rs.getInt(3), rs.getString(4), rs.getInt(5))); }, orderId);
        return jdbc.query("SELECT id, return_number, status, method, refund_cents, created_at FROM returns WHERE order_id = ? ORDER BY created_at",
                (rs, i) -> {
                    UUID rid = rs.getObject(1, UUID.class);
                    return new OrderView.ReturnView(rs.getString(2), rs.getString(3), rs.getString(4), rs.getInt(5),
                            rs.getTimestamp(6).toInstant(), lines.getOrDefault(rid, List.of()));
                }, orderId);
    }
}
