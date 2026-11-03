package com.otterworks.ottershops.catalog;

import java.time.Instant;
import java.util.List;

public record Product(
        String id,
        String name,
        String label,
        String department,
        String category,
        String fit,
        String description,
        String details,
        String materials,
        int listPriceCents,
        Integer markdownPriceCents,
        double rating,
        int reviewCount,
        boolean isNew,
        Instant createdAt,
        List<String> collections,
        List<ProductImage> images,
        List<Sku> skus,
        List<String> related) {

    public int totalStock() {
        return skus.stream().mapToInt(Sku::stock).sum();
    }

    public StockState stockState() {
        int total = totalStock();
        if (total == 0) return StockState.SOLD_OUT;
        if (total <= CatalogService.LOW_STOCK_PRODUCT) return StockState.LOW_STOCK;
        return StockState.IN_STOCK;
    }

    public enum StockState { IN_STOCK, LOW_STOCK, SOLD_OUT }
}
