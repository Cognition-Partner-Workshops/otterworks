package com.otterworks.ottershops.catalog;

import com.otterworks.ottershops.pricing.PriceInfo;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class ProductViews {
    private ProductViews() {}

    public record Swatch(String name, String hex, String family, String image, boolean soldOut) {}

    public record Card(String id, String name, String label, String department, String category, String fit,
                       PriceInfo price, String image, String hoverImage, List<Swatch> colors, List<String> sizes,
                       Product.StockState stockState, double rating, int reviewCount, boolean isNew,
                       List<String> collections) {}

    public record SkuView(String sku, String color, String size, int stock, boolean soldOut, boolean lowStock) {}

    public record Detail(String id, String name, String label, String department, String category, String fit,
                         String description, String details, String materials, PriceInfo price,
                         List<ProductImage> images, List<Swatch> colors, List<String> sizes, List<SkuView> skus,
                         Product.StockState stockState, double rating, int reviewCount, boolean isNew,
                         List<String> collections, List<Card> related) {}

    static List<Swatch> swatches(Product p, CatalogService catalog) {
        Map<String, List<Sku>> byColor = new LinkedHashMap<>();
        p.skus().forEach(s -> byColor.computeIfAbsent(s.color(), k -> new ArrayList<>()).add(s));
        List<Swatch> out = new ArrayList<>();
        byColor.forEach((color, skus) -> out.add(new Swatch(color, skus.get(0).colorHex(), skus.get(0).colorFamily(),
                catalog.imageFor(p, color), skus.stream().allMatch(s -> s.stock() == 0))));
        return out;
    }

    static List<String> sizes(Product p) {
        return p.skus().stream().sorted(Comparator.comparingInt(Sku::sizeOrder)).map(Sku::size).distinct().toList();
    }

    public static Card card(Product p, CatalogService catalog) {
        String hover = p.images().size() > 1 ? p.images().get(1).url() : null;
        return new Card(p.id(), p.name(), p.label(), p.department(), p.category(), p.fit(), catalog.price(p),
                p.images().isEmpty() ? null : p.images().get(0).url(), hover, swatches(p, catalog), sizes(p),
                p.stockState(), p.rating(), p.reviewCount(), p.isNew(), p.collections());
    }

    public static Detail detail(Product p, CatalogService catalog) {
        List<SkuView> skus = p.skus().stream()
                .map(s -> new SkuView(s.sku(), s.color(), s.size(), s.stock(), s.stock() == 0,
                        s.stock() > 0 && s.stock() <= CatalogService.LOW_STOCK_SKU))
                .toList();
        List<Card> related = p.related().stream().map(catalog::findProduct).flatMap(java.util.Optional::stream)
                .map(r -> card(r, catalog)).toList();
        return new Detail(p.id(), p.name(), p.label(), p.department(), p.category(), p.fit(), p.description(),
                p.details(), p.materials(), catalog.price(p), p.images(), swatches(p, catalog), sizes(p), skus,
                p.stockState(), p.rating(), p.reviewCount(), p.isNew(), p.collections(), related);
    }
}
