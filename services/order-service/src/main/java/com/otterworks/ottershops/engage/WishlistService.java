package com.otterworks.ottershops.engage;

import com.otterworks.ottershops.catalog.CatalogService;
import com.otterworks.ottershops.catalog.ProductViews;
import com.otterworks.ottershops.common.ApiException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

/** Favorites. A guest list is readable by whoever holds its id; once claimed it belongs to that member. */
@Service
public class WishlistService {
    public static final int MAX_ITEMS = 200;
    private final JdbcTemplate jdbc;
    private final CatalogService catalog;

    public WishlistService(JdbcTemplate jdbc, CatalogService catalog) {
        this.jdbc = jdbc;
        this.catalog = catalog;
    }

    public record Item(String productId, String color, Instant addedAt, ProductViews.Card product) {}

    public record View(UUID id, boolean member, List<Item> items, int count) {}

    record Row(UUID id, UUID customerId) {}

    Optional<Row> find(UUID id) {
        return jdbc.query("SELECT id, customer_id FROM wishlists WHERE id = ?",
                (rs, i) -> new Row(rs.getObject(1, UUID.class), rs.getObject(2, UUID.class)), id).stream().findFirst();
    }

    Optional<UUID> memberList(UUID customerId) {
        return jdbc.queryForList("SELECT id FROM wishlists WHERE customer_id = ?", UUID.class, customerId).stream().findFirst();
    }

    Row access(UUID id, UUID customerId) {
        Row row = find(id).orElseThrow(() -> ApiException.notFound("Wishlist"));
        if (row.customerId() != null && !row.customerId().equals(customerId)) throw ApiException.notFound("Wishlist");
        return row;
    }

    @Transactional
    public View create(UUID customerId) {
        if (customerId != null) {
            Optional<UUID> existing = memberList(customerId);
            if (existing.isPresent()) return view(existing.get(), customerId);
        }
        UUID id = UUID.randomUUID();
        jdbc.update("INSERT INTO wishlists (id, customer_id) VALUES (?, ?)", id, customerId);
        return view(id, customerId);
    }

    public View view(UUID id, UUID customerId) {
        Row row = access(id, customerId);
        List<Item> items = jdbc.query("SELECT product_id, color, added_at FROM wishlist_items WHERE wishlist_id = ? ORDER BY added_at DESC, product_id",
                (rs, i) -> {
                    String pid = rs.getString(1);
                    String color = rs.getString(2);
                    Instant added = rs.getTimestamp(3).toInstant();
                    return catalog.findProduct(pid).map(p -> new Item(pid, color, added, ProductViews.card(p, catalog))).orElse(null);
                }, id).stream().filter(java.util.Objects::nonNull).toList();
        return new View(row.id(), row.customerId() != null, items, items.size());
    }

    @Transactional
    public View add(UUID id, UUID customerId, String productId, String color) {
        access(id, customerId);
        catalog.product(productId);
        Integer count = jdbc.queryForObject("SELECT count(*) FROM wishlist_items WHERE wishlist_id = ?", Integer.class, id);
        if (count != null && count >= MAX_ITEMS) throw ApiException.badRequest("WISHLIST_FULL", "Your favorites list is full");
        jdbc.update("""
                INSERT INTO wishlist_items (wishlist_id, product_id, color) VALUES (?, ?, ?)
                ON CONFLICT (wishlist_id, product_id) DO UPDATE SET color = COALESCE(EXCLUDED.color, wishlist_items.color)""",
                id, productId, color);
        jdbc.update("UPDATE wishlists SET updated_at = now() WHERE id = ?", id);
        return view(id, customerId);
    }

    @Transactional
    public View remove(UUID id, UUID customerId, String productId) {
        access(id, customerId);
        jdbc.update("DELETE FROM wishlist_items WHERE wishlist_id = ? AND product_id = ?", id, productId);
        jdbc.update("UPDATE wishlists SET updated_at = now() WHERE id = ?", id);
        return view(id, customerId);
    }

    /** Adopts or merges a guest list into the signed-in member's list and returns the member list. */
    @Transactional
    public View claim(UUID guestId, UUID customerId) {
        if (customerId == null) throw ApiException.unauthorized();
        Optional<UUID> member = memberList(customerId);
        Optional<Row> guest = guestId == null ? Optional.empty() : find(guestId).filter(r -> r.customerId() == null);
        if (guest.isEmpty()) return member.map(m -> view(m, customerId)).orElseGet(() -> create(customerId));
        if (member.isEmpty()) {
            jdbc.update("UPDATE wishlists SET customer_id = ?, updated_at = now() WHERE id = ?", customerId, guestId);
            return view(guestId, customerId);
        }
        jdbc.update("""
                INSERT INTO wishlist_items (wishlist_id, product_id, color, added_at)
                SELECT ?, product_id, color, added_at FROM wishlist_items WHERE wishlist_id = ?
                ON CONFLICT (wishlist_id, product_id) DO NOTHING""", member.get(), guestId);
        jdbc.update("DELETE FROM wishlist_items WHERE wishlist_id = ?", guestId);
        return view(member.get(), customerId);
    }
}
