package com.otterworks.ottershops.catalog;

import com.otterworks.ottershops.pricing.PricingService;
import com.otterworks.ottershops.pricing.Promotion;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.Instant;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api")
public class CatalogController {
    private final CatalogService catalog;
    private final PricingService pricing;

    public CatalogController(CatalogService catalog, PricingService pricing) {
        this.catalog = catalog;
        this.pricing = pricing;
    }

    public record PromoCodeView(String code, String description, int minSubtotalCents) {}

    public record PromotionView(boolean active, String id, String name, String headline, String subhead,
                                String bannerText, Instant startsAt, Instant endsAt, int percentOff,
                                List<String> excludedCollections, List<PromoCodeView> codes) {}

    @GetMapping("/promotions/active")
    public PromotionView activePromotion() {
        return pricing.activePromotion()
                .map(CatalogController::view)
                .orElse(new PromotionView(false, null, null, null, null, null, null, null, 0, List.of(), List.of()));
    }

    private static PromotionView view(Promotion p) {
        return new PromotionView(true, p.id(), p.name(), p.headline(), p.subhead(), p.bannerText(), p.startsAt(),
                p.endsAt(), p.percentOff(), p.excludedCollections(),
                p.codes().stream().map(c -> new PromoCodeView(c.code(), c.description(), c.minSubtotalCents())).toList());
    }

    @GetMapping("/collections")
    public List<CollectionInfo> collections() {
        return catalog.collections();
    }

    @GetMapping("/products")
    public ProductQuery.Result products(
            @RequestParam(required = false) String department,
            @RequestParam(required = false) String collection,
            @RequestParam(required = false) String category,
            @RequestParam(required = false) String size,
            @RequestParam(required = false) String color,
            @RequestParam(required = false) String fit,
            @RequestParam(required = false) Integer priceMin,
            @RequestParam(required = false) Integer priceMax,
            @RequestParam(required = false) String q,
            @RequestParam(defaultValue = "featured") String sort,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "48") int pageSize) {
        return new ProductQuery(department, collection, ProductQuery.csv(category), ProductQuery.csv(size),
                ProductQuery.csv(color), ProductQuery.csv(fit), priceMin, priceMax, q, sort, page, pageSize)
                .run(catalog);
    }

    @GetMapping("/products/{id}")
    public ProductViews.Detail product(@PathVariable String id) {
        return ProductViews.detail(catalog.product(id), catalog);
    }

    @GetMapping("/stores")
    public Map<String, Object> stores(@RequestParam(required = false) String q) {
        return Map.of("stores", catalog.searchStores(q));
    }
}
