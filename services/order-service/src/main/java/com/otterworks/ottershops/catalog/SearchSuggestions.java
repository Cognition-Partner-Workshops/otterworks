package com.otterworks.ottershops.catalog;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/** Typeahead: ranked product matches plus category and collection shortcuts for the search box. */
public final class SearchSuggestions {
    private SearchSuggestions() {}

    public record Suggestion(String type, String label, String href) {}

    public record Result(String query, List<Suggestion> terms, List<ProductViews.Card> products, int totalProducts) {}

    static int score(Product p, String q) {
        String name = p.name().toLowerCase(Locale.ROOT);
        if (name.startsWith(q)) return 0;
        if (name.contains(" " + q)) return 1;
        if (name.contains(q)) return 2;
        if (p.category().toLowerCase(Locale.ROOT).contains(q)) return 3;
        if (p.label() != null && p.label().toLowerCase(Locale.ROOT).contains(q)) return 4;
        if (p.collections().stream().anyMatch(c -> c.replace('-', ' ').contains(q))) return 5;
        return -1;
    }

    public static Result suggest(String raw, CatalogService catalog, int limit) {
        String q = raw == null ? "" : raw.trim().toLowerCase(Locale.ROOT);
        if (q.length() < 2) return new Result(q, List.of(), List.of(), 0);
        List<Product> matches = catalog.products().stream()
                .filter(p -> score(p, q) >= 0)
                .sorted(Comparator.comparingInt((Product p) -> score(p, q))
                        .thenComparing((Product p) -> p.stockState() == Product.StockState.SOLD_OUT)
                        .thenComparing(Comparator.comparingInt(Product::reviewCount).reversed()))
                .toList();
        Map<String, Suggestion> terms = new LinkedHashMap<>();
        for (Product p : matches) {
            String cat = p.category();
            if (cat.toLowerCase(Locale.ROOT).contains(q) || score(p, q) <= 2) {
                String key = p.department() + "/" + cat;
                terms.putIfAbsent(key, new Suggestion("category", cat + " in " + capitalize(p.department()),
                        "/c/" + p.department() + "?category="
                        + java.net.URLEncoder.encode(cat.toLowerCase(Locale.ROOT), java.nio.charset.StandardCharsets.UTF_8)));
            }
            if (terms.size() >= 4) break;
        }
        List<Suggestion> list = new ArrayList<>(terms.values());
        for (CollectionInfo c : catalog.collections()) {
            if (list.size() >= 6) break;
            if (c.name().toLowerCase(Locale.ROOT).contains(q)) {
                list.add(new Suggestion("collection", c.name(), "/c/" + c.slug()));
            }
        }
        List<ProductViews.Card> cards = matches.stream().limit(limit).map(p -> ProductViews.card(p, catalog)).toList();
        return new Result(q, list, cards, matches.size());
    }

    private static String capitalize(String s) {
        return s.isEmpty() ? s : Character.toUpperCase(s.charAt(0)) + s.substring(1);
    }
}
