package com.otterworks.ottershops.engage;

import com.otterworks.ottershops.catalog.CatalogService;
import com.otterworks.ottershops.catalog.Sku;
import com.otterworks.ottershops.common.ApiException;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.Locale;
import java.util.UUID;
import java.util.regex.Pattern;

@Service
public class StockNotificationService {
    static final Pattern EMAIL = Pattern.compile("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$");
    private final JdbcTemplate jdbc;
    private final CatalogService catalog;

    public StockNotificationService(JdbcTemplate jdbc, CatalogService catalog) {
        this.jdbc = jdbc;
        this.catalog = catalog;
    }

    public record Subscription(String sku, String productId, String color, String size, String email, String status) {}

    public Subscription subscribe(String skuId, String rawEmail, UUID customerId) {
        Sku sku = catalog.findSku(skuId).orElseThrow(() -> ApiException.notFound("Item"));
        String email = rawEmail == null ? "" : rawEmail.trim().toLowerCase(Locale.ROOT);
        if (!EMAIL.matcher(email).matches()) throw ApiException.badRequest("EMAIL_INVALID", "Enter a valid email address");
        if (sku.stock() > 0) {
            throw new ApiException(HttpStatus.CONFLICT, "IN_STOCK", "Good news: this size is in stock now");
        }
        jdbc.update("""
                INSERT INTO stock_notifications (sku, email, customer_id) VALUES (?, ?, ?)
                ON CONFLICT (sku, email) DO UPDATE SET status = 'PENDING', updated_at = now(),
                  customer_id = COALESCE(EXCLUDED.customer_id, stock_notifications.customer_id)""", skuId, email, customerId);
        return new Subscription(sku.sku(), sku.productId(), sku.color(), sku.size(), email, "PENDING");
    }
}
