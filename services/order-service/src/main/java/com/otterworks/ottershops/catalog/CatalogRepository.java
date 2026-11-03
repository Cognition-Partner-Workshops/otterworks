package com.otterworks.ottershops.catalog;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.sql.Timestamp;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Repository
public class CatalogRepository {
    private final JdbcTemplate jdbc;

    public CatalogRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public List<Product> loadProducts() {
        Map<String, List<String>> collections = new LinkedHashMap<>();
        jdbc.query("SELECT product_id, collection_slug FROM product_collections ORDER BY collection_slug",
                rs -> { collections.computeIfAbsent(rs.getString(1), k -> new ArrayList<>()).add(rs.getString(2)); });
        Map<String, List<ProductImage>> images = new LinkedHashMap<>();
        jdbc.query("SELECT product_id, position, url, alt, color FROM product_images ORDER BY product_id, position",
                rs -> {
                    images.computeIfAbsent(rs.getString(1), k -> new ArrayList<>())
                            .add(new ProductImage(rs.getInt(2), rs.getString(3), rs.getString(4), rs.getString(5)));
                });
        Map<String, List<Sku>> skus = new LinkedHashMap<>();
        jdbc.query("SELECT sku, product_id, color, color_hex, color_family, size, size_order, stock FROM skus ORDER BY product_id, color, size_order",
                rs -> {
                    skus.computeIfAbsent(rs.getString(2), k -> new ArrayList<>())
                            .add(new Sku(rs.getString(1), rs.getString(2), rs.getString(3), rs.getString(4),
                                    rs.getString(5), rs.getString(6), rs.getInt(7), rs.getInt(8)));
                });
        Map<String, List<String>> related = new LinkedHashMap<>();
        jdbc.query("SELECT product_id, related_id FROM product_links ORDER BY product_id, position",
                rs -> { related.computeIfAbsent(rs.getString(1), k -> new ArrayList<>()).add(rs.getString(2)); });

        return jdbc.query("""
                SELECT id, name, label, department, category, fit, description, details, materials,
                       list_price_cents, markdown_price_cents, rating, review_count, is_new, created_at
                FROM products ORDER BY id""", (rs, i) -> {
            String id = rs.getString("id");
            Integer markdown = (Integer) rs.getObject("markdown_price_cents");
            Timestamp created = rs.getTimestamp("created_at");
            return new Product(id, rs.getString("name"), rs.getString("label"), rs.getString("department"),
                    rs.getString("category"), rs.getString("fit"), rs.getString("description"),
                    rs.getString("details"), rs.getString("materials"), rs.getInt("list_price_cents"), markdown,
                    rs.getDouble("rating"), rs.getInt("review_count"), rs.getBoolean("is_new"),
                    created == null ? null : created.toInstant(),
                    List.copyOf(collections.getOrDefault(id, List.of())),
                    List.copyOf(images.getOrDefault(id, List.of())),
                    List.copyOf(skus.getOrDefault(id, List.of())),
                    List.copyOf(related.getOrDefault(id, List.of())));
        });
    }

    public List<CollectionInfo> loadCollections() {
        return jdbc.query("SELECT slug, name, department, description, hero_image, sort_order FROM collections ORDER BY sort_order, slug",
                (rs, i) -> new CollectionInfo(rs.getString(1), rs.getString(2), rs.getString(3), rs.getString(4),
                        rs.getString(5), rs.getInt(6)));
    }

    public List<Store> loadStores() {
        return jdbc.query("""
                SELECT id, name, address, city, state, zip, phone, hours, latitude, longitude, pickup_enabled, pickup_ready_hours
                FROM stores ORDER BY state, city, name""",
                (rs, i) -> new Store(rs.getString(1), rs.getString(2), rs.getString(3), rs.getString(4),
                        rs.getString(5), rs.getString(6), rs.getString(7), rs.getString(8),
                        (Double) rs.getObject(9), (Double) rs.getObject(10), rs.getBoolean(11), rs.getInt(12)));
    }
}
