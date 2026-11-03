package com.otterworks.ottershops.catalog;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.function.Predicate;
import java.util.stream.Collectors;

/** PLP filtering, sorting, faceting and paging over the in-memory catalog. */
public record ProductQuery(String department, String collection, Set<String> categories, Set<String> sizes,
                           Set<String> colors, Set<String> fits, Integer priceMin, Integer priceMax, Boolean onSale, String q,
                           String sort, int page, int pageSize) {

    public record Facet(String value, int count) {}

    public record Facets(List<Facet> categories, List<Facet> sizes, List<Facet> colors, List<Facet> fits,
                         int priceMinCents, int priceMaxCents) {}

    public record Result(List<ProductViews.Card> items, int total, int page, int pageSize, Facets facets) {}

    public static Set<String> csv(String value) {
        if (value == null || value.isBlank()) return Set.of();
        return Arrays.stream(value.split(",")).map(String::trim).filter(s -> !s.isEmpty())
                .map(s -> s.toLowerCase(Locale.ROOT)).collect(Collectors.toSet());
    }

    public Result run(CatalogService catalog) {
        List<Product> scoped = catalog.products().stream().filter(this::inScope).toList();
        Facets facets = facets(scoped, catalog);
        List<Product> filtered = scoped.stream()
                .filter(matchAny(categories, p -> List.of(p.category())))
                .filter(matchAny(sizes, p -> p.skus().stream().filter(s -> s.stock() > 0).map(Sku::size).toList()))
                .filter(matchAny(colors, p -> p.skus().stream().map(Sku::colorFamily).toList()))
                .filter(matchAny(fits, p -> p.fit() == null ? List.of() : List.of(p.fit())))
                .filter(p -> priceMin == null || catalog.price(p).priceCents() >= priceMin)
                .filter(p -> priceMax == null || catalog.price(p).priceCents() <= priceMax)
                .filter(p -> !Boolean.TRUE.equals(onSale) || catalog.price(p).onSale())
                .sorted(comparator(catalog))
                .toList();
        int size = Math.max(1, Math.min(pageSize, 200));
        int from = Math.min(Math.max(0, page - 1) * size, filtered.size());
        List<ProductViews.Card> items = filtered.subList(from, Math.min(from + size, filtered.size())).stream()
                .map(p -> ProductViews.card(p, catalog)).toList();
        return new Result(items, filtered.size(), Math.max(1, page), size, facets);
    }

    private boolean inScope(Product p) {
        if (department != null && !department.isBlank() && !p.department().equalsIgnoreCase(department)) return false;
        if (collection != null && !collection.isBlank() && !p.collections().contains(collection.toLowerCase(Locale.ROOT))) return false;
        if (q != null && !q.isBlank()) {
            String needle = q.trim().toLowerCase(Locale.ROOT);
            String hay = String.join(" ", p.name(), p.category(), p.department(),
                    p.description() == null ? "" : p.description(), String.join(" ", p.collections()))
                    .toLowerCase(Locale.ROOT);
            return Arrays.stream(needle.split("\\s+")).allMatch(hay::contains);
        }
        return true;
    }

    private static Predicate<Product> matchAny(Set<String> wanted, java.util.function.Function<Product, Collection<String>> values) {
        if (wanted.isEmpty()) return p -> true;
        return p -> values.apply(p).stream().anyMatch(v -> wanted.contains(v.toLowerCase(Locale.ROOT)));
    }

    private Comparator<Product> comparator(CatalogService catalog) {
        Comparator<Product> byPrice = Comparator.comparingInt(p -> catalog.price(p).priceCents());
        Comparator<Product> soldOutLast = Comparator.comparing(p -> p.stockState() == Product.StockState.SOLD_OUT);
        Comparator<Product> base = switch (sort == null ? "featured" : sort) {
            case "price-asc" -> byPrice;
            case "price-desc" -> byPrice.reversed();
            case "newest" -> Comparator.comparing(Product::isNew).reversed()
                    .thenComparing(Product::createdAt, Comparator.nullsLast(Comparator.reverseOrder()));
            case "rating" -> Comparator.comparingDouble(Product::rating).reversed()
                    .thenComparing(Comparator.comparingInt(Product::reviewCount).reversed());
            case "discount" -> Comparator.comparingInt((Product p) -> catalog.price(p).percentOff()).reversed();
            default -> Comparator.comparingInt((Product p) -> p.reviewCount()).reversed();
        };
        return soldOutLast.thenComparing(base).thenComparing(Product::id);
    }

    private static Facets facets(List<Product> scoped, CatalogService catalog) {
        Map<String, Integer> cats = new TreeMap<>();
        Map<String, int[]> sizes = new LinkedHashMap<>();
        Map<String, Integer> colors = new TreeMap<>();
        Map<String, Integer> fits = new TreeMap<>();
        int min = Integer.MAX_VALUE, max = 0;
        List<Sku> allSkus = new ArrayList<>();
        for (Product p : scoped) {
            cats.merge(p.category(), 1, Integer::sum);
            if (p.fit() != null) fits.merge(p.fit(), 1, Integer::sum);
            p.skus().stream().map(Sku::colorFamily).distinct().forEach(c -> colors.merge(c, 1, Integer::sum));
            allSkus.addAll(p.skus());
            int price = catalog.price(p).priceCents();
            min = Math.min(min, price);
            max = Math.max(max, price);
        }
        allSkus.stream().sorted(Comparator.comparingInt(Sku::sizeOrder))
                .forEach(s -> sizes.computeIfAbsent(s.size(), k -> new int[]{0}));
        for (Product p : scoped) {
            p.skus().stream().map(Sku::size).distinct().forEach(sz -> sizes.get(sz)[0]++);
        }
        return new Facets(toFacets(cats), sizes.entrySet().stream().map(e -> new Facet(e.getKey(), e.getValue()[0])).toList(),
                toFacets(colors), toFacets(fits), scoped.isEmpty() ? 0 : min, max);
    }

    private static List<Facet> toFacets(Map<String, Integer> m) {
        return m.entrySet().stream().map(e -> new Facet(e.getKey(), e.getValue())).toList();
    }
}
