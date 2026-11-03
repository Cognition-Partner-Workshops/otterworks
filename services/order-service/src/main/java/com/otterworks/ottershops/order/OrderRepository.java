package com.otterworks.ottershops.order;

import com.otterworks.ottershops.catalog.CatalogService;
import com.otterworks.ottershops.catalog.Store;
import com.otterworks.ottershops.pricing.Fee;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public class OrderRepository {
    private final JdbcTemplate jdbc;
    private final CatalogService catalog;

    public OrderRepository(JdbcTemplate jdbc, CatalogService catalog) {
        this.jdbc = jdbc;
        this.catalog = catalog;
    }

    public String nextOrderNumber() {
        return "OS-" + jdbc.queryForObject("SELECT nextval('order_number_seq')", Long.class);
    }

    public String nextInvoiceNumber() {
        return "INV-" + jdbc.queryForObject("SELECT nextval('invoice_number_seq')", Long.class);
    }

    public void insertOrder(UUID id, String number, UUID customerId, String email, String fulfillment, String method,
                            String storeId, OrderView.Address a, String phone, String promo, int subtotal, int discount,
                            int shipping, int fees, BigDecimal taxRate, int tax, int total, String provider, String reference,
                            String brand, String last4) {
        jdbc.update("""
                INSERT INTO orders (id, order_number, customer_id, email, status, fulfillment, shipping_method, store_id,
                  ship_name, ship_line1, ship_line2, ship_city, ship_state, ship_zip, phone, promo_code,
                  subtotal_cents, discount_cents, shipping_cents, fees_cents, tax_rate, tax_cents, total_cents,
                  payment_provider, payment_reference, card_brand, card_last4)
                VALUES (?, ?, ?, ?, 'PLACED', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                id, number, customerId, email, fulfillment, method, storeId,
                a == null ? null : a.name(), a == null ? null : a.line1(), a == null ? null : a.line2(),
                a == null ? null : a.city(), a == null ? null : a.state(), a == null ? null : a.zip(),
                phone, promo, subtotal, discount, shipping, fees, taxRate, tax, total, provider, reference, brand, last4);
    }

    public void insertLine(UUID orderId, OrderView.Line l) {
        jdbc.update("""
                INSERT INTO order_lines (order_id, line_no, sku, product_id, name, color, size, image_url, quantity,
                  unit_list_cents, unit_price_cents, discount_cents, line_total_cents)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                orderId, l.lineNo(), l.sku(), l.productId(), l.name(), l.color(), l.size(), l.image(), l.quantity(),
                l.unitListCents(), l.unitPriceCents(), l.discountCents(), l.lineTotalCents());
    }

    public void insertFee(UUID orderId, Fee f) {
        jdbc.update("INSERT INTO order_fees (order_id, code, label, amount_cents) VALUES (?, ?, ?, ?)",
                orderId, f.code(), f.label(), f.amountCents());
    }

    public void insertInvoice(String number, UUID orderId, int total) {
        jdbc.update("INSERT INTO invoices (invoice_number, order_id, total_cents) VALUES (?, ?, ?)", number, orderId, total);
    }

    public Optional<OrderView> findByNumber(String number) {
        return jdbc.query("""
                SELECT o.*, i.invoice_number FROM orders o LEFT JOIN invoices i ON i.order_id = o.id
                WHERE o.order_number = ?""", (rs, n) -> map(rs), number.trim().toUpperCase()).stream().findFirst();
    }

    public Optional<UUID> ownerOf(String number) {
        return jdbc.queryForList("SELECT customer_id FROM orders WHERE order_number = ? AND customer_id IS NOT NULL",
                UUID.class, number).stream().findFirst();
    }

    public List<OrderView.Summary> forCustomer(UUID customerId) {
        return jdbc.query("""
                SELECT o.order_number, o.status, o.fulfillment, o.total_cents, o.created_at,
                       (SELECT sum(quantity) FROM order_lines l WHERE l.order_id = o.id) AS items,
                       (SELECT image_url FROM order_lines l WHERE l.order_id = o.id ORDER BY line_no LIMIT 1) AS image
                FROM orders o WHERE o.customer_id = ? ORDER BY o.created_at DESC""",
                (rs, n) -> new OrderView.Summary(rs.getString(1), rs.getString(2), rs.getString(3), rs.getInt(6),
                        rs.getInt(4), rs.getTimestamp(5).toInstant(), rs.getString(7)), customerId);
    }

    private OrderView map(ResultSet rs) throws SQLException {
        UUID id = rs.getObject("id", UUID.class);
        List<OrderView.Line> lines = jdbc.query("SELECT * FROM order_lines WHERE order_id = ? ORDER BY line_no",
                (r, n) -> new OrderView.Line(r.getInt("line_no"), r.getString("sku"), r.getString("product_id"),
                        r.getString("name"), r.getString("color"), r.getString("size"), r.getString("image_url"),
                        r.getInt("quantity"), r.getInt("unit_list_cents"), r.getInt("unit_price_cents"),
                        r.getInt("discount_cents"), r.getInt("line_total_cents")), id);
        List<Fee> fees = jdbc.query("SELECT code, label, amount_cents FROM order_fees WHERE order_id = ? ORDER BY code",
                (r, n) -> new Fee(r.getString(1), r.getString(2), r.getInt(3)), id);
        String fulfillment = rs.getString("fulfillment");
        OrderView.Pickup pickup = null;
        OrderView.Address ship = null;
        String storeId = rs.getString("store_id");
        if ("PICKUP".equals(fulfillment) && storeId != null) {
            Store s = catalog.store(storeId);
            pickup = new OrderView.Pickup(s.id(), s.name(), s.address(), s.city(), s.state(), s.zip(), s.pickupReadyHours());
        } else {
            ship = new OrderView.Address(rs.getString("ship_name"), rs.getString("ship_line1"), rs.getString("ship_line2"),
                    rs.getString("ship_city"), rs.getString("ship_state"), rs.getString("ship_zip"));
        }
        int subtotal = rs.getInt("subtotal_cents");
        int discount = rs.getInt("discount_cents");
        int shipping = rs.getInt("shipping_cents");
        int tax = rs.getInt("tax_cents");
        int base = subtotal - discount + shipping;
        BigDecimal rate = rs.getBigDecimal("tax_rate");
        if (rate == null) {
            rate = base == 0 ? BigDecimal.ZERO
                    : BigDecimal.valueOf(tax * 100L).divide(BigDecimal.valueOf(base), 2, RoundingMode.HALF_UP);
        }
        int total = rs.getInt("total_cents");
        boolean member = rs.getObject("customer_id") != null;
        return new OrderView(id, rs.getString("order_number"), rs.getString("invoice_number"), rs.getString("email"),
                rs.getString("status"), fulfillment, rs.getString("shipping_method"), pickup, ship, rs.getString("phone"),
                rs.getString("promo_code"), lines, subtotal, discount, shipping, fees, rs.getInt("fees_cents"), rate, tax,
                total, rs.getString("card_brand"), rs.getString("card_last4"), member ? total / 100 : 0,
                rs.getTimestamp("created_at").toInstant());
    }
}
