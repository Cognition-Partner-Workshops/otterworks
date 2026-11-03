package com.otterworks.ottershops.catalog;

import com.otterworks.ottershops.common.ApiException;
import com.otterworks.ottershops.pricing.PriceInfo;
import com.otterworks.ottershops.pricing.PricingService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.function.Function;
import java.util.stream.Collectors;

/**
 * In-memory read model of the catalog. The catalog is small (a few hundred products), so it is
 * loaded whole and refreshed on a timer and after every order, which keeps stock badges current.
 */
@Service
public class CatalogService {
    public static final int LOW_STOCK_SKU = 5;
    public static final int LOW_STOCK_PRODUCT = 10;
    private static final Logger log = LoggerFactory.getLogger(CatalogService.class);

    private final CatalogRepository repo;
    private final PricingService pricing;
    private volatile Snapshot snapshot = new Snapshot(List.of(), Map.of(), Map.of(), List.of(), List.of());

    public CatalogService(CatalogRepository repo, PricingService pricing) {
        this.repo = repo;
        this.pricing = pricing;
    }

    record Snapshot(List<Product> products, Map<String, Product> byId, Map<String, Sku> bySku,
                    List<CollectionInfo> collections, List<Store> stores) {}

    @Scheduled(initialDelay = 0, fixedDelayString = "${ottershops.catalog.refresh-ms:60000}")
    public void refresh() {
        List<Product> products = repo.loadProducts();
        Map<String, Product> byId = products.stream()
                .collect(Collectors.toMap(Product::id, Function.identity(), (a, b) -> a, LinkedHashMap::new));
        Map<String, Sku> bySku = products.stream().flatMap(p -> p.skus().stream())
                .collect(Collectors.toMap(Sku::sku, Function.identity()));
        snapshot = new Snapshot(products, byId, bySku, repo.loadCollections(), repo.loadStores());
        log.debug("catalog refreshed: {} products, {} skus", products.size(), bySku.size());
    }

    public List<Product> products() { return snapshot.products(); }
    public List<CollectionInfo> collections() { return snapshot.collections(); }
    public List<Store> stores() { return snapshot.stores(); }

    public Product product(String id) {
        Product p = snapshot.byId().get(id);
        if (p == null) throw ApiException.notFound("Product");
        return p;
    }

    public Optional<Product> findProduct(String id) {
        return Optional.ofNullable(snapshot.byId().get(id));
    }

    public Optional<Sku> findSku(String sku) {
        return Optional.ofNullable(snapshot.bySku().get(sku));
    }

    public Store store(String id) {
        return snapshot.stores().stream().filter(s -> s.id().equals(id)).findFirst()
                .orElseThrow(() -> ApiException.notFound("Store"));
    }

    public PriceInfo price(Product p) {
        return pricing.price(p.listPriceCents(), p.markdownPriceCents(), p.collections());
    }

    public String imageFor(Product p, String color) {
        return p.images().stream().filter(i -> color != null && color.equals(i.color())).findFirst()
                .or(() -> p.images().stream().findFirst())
                .map(ProductImage::url).orElse(null);
    }

    public List<Store> searchStores(String query) {
        String q = query == null ? "" : query.trim().toLowerCase(Locale.ROOT);
        if (q.isEmpty()) return stores();
        if (q.chars().allMatch(Character::isDigit)) {
            // Rank by numeric distance between ZIPs: a cheap, deterministic stand-in for geocoding.
            int zip = Integer.parseInt(q.length() > 5 ? q.substring(0, 5) : q);
            return stores().stream()
                    .sorted(Comparator.comparingInt(s -> Math.abs(parseZip(s.zip()) - zip)))
                    .limit(8)
                    .toList();
        }
        return stores().stream()
                .filter(s -> s.city().toLowerCase(Locale.ROOT).contains(q)
                        || s.name().toLowerCase(Locale.ROOT).contains(q)
                        || s.state().equalsIgnoreCase(q))
                .toList();
    }

    private static int parseZip(String zip) {
        try {
            return Integer.parseInt(zip.substring(0, Math.min(5, zip.length())));
        } catch (RuntimeException e) {
            return 0;
        }
    }
}
