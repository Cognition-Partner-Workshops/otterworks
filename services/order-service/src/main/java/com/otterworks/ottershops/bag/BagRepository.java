package com.otterworks.ottershops.bag;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

@Repository
public class BagRepository {
    private final JdbcTemplate jdbc;

    public BagRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public record BagRow(UUID id, UUID customerId, String promoCode, String status) {
        public boolean open() { return "OPEN".equals(status); }
    }

    public UUID create(UUID customerId) {
        UUID id = UUID.randomUUID();
        jdbc.update("INSERT INTO bags (id, customer_id) VALUES (?, ?)", id, customerId);
        return id;
    }

    public Optional<BagRow> find(UUID id, boolean forUpdate) {
        String sql = "SELECT id, customer_id, promo_code, status FROM bags WHERE id = ?" + (forUpdate ? " FOR UPDATE" : "");
        return jdbc.query(sql, (rs, i) -> new BagRow(rs.getObject(1, UUID.class), rs.getObject(2, UUID.class),
                rs.getString(3), rs.getString(4)), id).stream().findFirst();
    }

    public Optional<UUID> openBagFor(UUID customerId) {
        return jdbc.queryForList("SELECT id FROM bags WHERE customer_id = ? AND status = 'OPEN' ORDER BY updated_at DESC LIMIT 1",
                UUID.class, customerId).stream().findFirst();
    }

    /** Items in insertion order, keyed by SKU. */
    public Map<String, Integer> items(UUID bagId) {
        Map<String, Integer> items = new LinkedHashMap<>();
        jdbc.query("SELECT sku, quantity FROM bag_items WHERE bag_id = ? ORDER BY added_at, sku",
                rs -> { items.put(rs.getString(1), rs.getInt(2)); }, bagId);
        return items;
    }

    public void setQuantity(UUID bagId, String sku, int quantity) {
        jdbc.update("""
                INSERT INTO bag_items (bag_id, sku, quantity) VALUES (?, ?, ?)
                ON CONFLICT (bag_id, sku) DO UPDATE SET quantity = EXCLUDED.quantity""", bagId, sku, quantity);
        touch(bagId);
    }

    public void removeItem(UUID bagId, String sku) {
        jdbc.update("DELETE FROM bag_items WHERE bag_id = ? AND sku = ?", bagId, sku);
        touch(bagId);
    }

    public void setPromo(UUID bagId, String code) {
        jdbc.update("UPDATE bags SET promo_code = ?, updated_at = now() WHERE id = ?", code, bagId);
    }

    public void assignCustomer(UUID bagId, UUID customerId) {
        jdbc.update("UPDATE bags SET customer_id = ?, updated_at = now() WHERE id = ?", customerId, bagId);
    }

    public void markConverted(UUID bagId) {
        jdbc.update("UPDATE bags SET status = 'CONVERTED', updated_at = now() WHERE id = ?", bagId);
    }

    private void touch(UUID bagId) {
        jdbc.update("UPDATE bags SET updated_at = now() WHERE id = ?", bagId);
    }

    public List<String> saved(UUID bagId) {
        return jdbc.queryForList("SELECT sku FROM bag_saved_items WHERE bag_id = ? ORDER BY saved_at DESC, sku", String.class, bagId);
    }

    public void save(UUID bagId, String sku) {
        jdbc.update("INSERT INTO bag_saved_items (bag_id, sku) VALUES (?, ?) ON CONFLICT (bag_id, sku) DO UPDATE SET saved_at = now()", bagId, sku);
        touch(bagId);
    }

    public void unsave(UUID bagId, String sku) {
        jdbc.update("DELETE FROM bag_saved_items WHERE bag_id = ? AND sku = ?", bagId, sku);
        touch(bagId);
    }
}
