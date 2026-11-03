package com.otterworks.ottershops.rewards;

import com.otterworks.ottershops.auth.CustomerRepository;
import com.otterworks.ottershops.bag.PricedBag;
import com.otterworks.ottershops.catalog.CatalogService;
import com.otterworks.ottershops.pricing.PricingService;
import java.util.List;
import java.util.UUID;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

/**
 * Members earn 1 point per whole dollar of merchandise, after discounts. Shipping, fees, tax and gift cards
 * don't earn. Every change to a balance is written to the ledger.
 */
@Service
public class RewardsService {
    public static final int CENTS_PER_POINT = 100;

    private final JdbcTemplate jdbc;
    private final CustomerRepository customers;
    private final CatalogService catalog;
    private final PricingService pricing;

    public RewardsService(JdbcTemplate jdbc, CustomerRepository customers, CatalogService catalog, PricingService pricing) {
        this.jdbc = jdbc;
        this.customers = customers;
        this.catalog = catalog;
        this.pricing = pricing;
    }

    public int earn(UUID customerId, UUID orderId, List<PricedBag.Line> lines) {
        long earning = lines.stream()
                .filter(l -> catalog.findProduct(l.productId()).map(p -> !pricing.excluded(p.collections())).orElse(true))
                .mapToLong(PricedBag.Line::lineTotalCents)
                .sum();
        int points = (int) (earning / CENTS_PER_POINT);
        record(customerId, orderId, "EARN", points, null);
        return points;
    }

    public void record(UUID customerId, UUID orderId, String kind, int points, String note) {
        jdbc.update("INSERT INTO rewards_ledger (customer_id, order_id, kind, points, note) VALUES (?, ?, ?, ?, ?)",
                customerId, orderId, kind, points, note);
        if (points != 0) customers.addPoints(customerId, points);
    }
}
