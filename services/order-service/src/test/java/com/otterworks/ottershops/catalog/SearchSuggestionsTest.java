package com.otterworks.ottershops.catalog;

import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class SearchSuggestionsTest {
    static Product product(String id, String name, String category, int reviews, int stock) {
        return new Product(id, name, null, "women", category, "Relaxed", "", "", "", 3000, null, 4.5, reviews, false,
                Instant.EPOCH, List.of("women"), List.of(), List.of(new Sku(id + "-S", id, "Navy", "#000", "blue", "S", 1, stock)),
                List.of());
    }

    static CatalogService catalog(List<Product> products) {
        CatalogService c = mock(CatalogService.class);
        when(c.products()).thenReturn(products);
        when(c.collections()).thenReturn(List.of(new CollectionInfo("denim-shop", "Denim Shop", null, "", null, 1)));
        return c;
    }

    @Test
    void shortQueriesReturnNothing() {
        assertEquals(0, SearchSuggestions.suggest("d", catalog(List.of(product("P1", "Denim Jacket", "Jackets", 1, 5))), 6).totalProducts());
    }

    @Test
    void prefixMatchesRankFirstAndInStockBeforeSoldOut() {
        CatalogService c = catalog(List.of(
                product("P1", "Washed Denim Shirt", "Shirts", 900, 5),
                product("P2", "Denim Jacket", "Jackets", 10, 0),
                product("P3", "Denim Skirt", "Skirts", 5, 5)));
        SearchSuggestions.Result r = SearchSuggestions.suggest("Denim", c, 6);
        assertEquals(3, r.totalProducts());
        assertEquals(List.of("P3", "P2", "P1"), r.products().stream().map(ProductViews.Card::id).toList());
        assertTrue(r.terms().stream().anyMatch(t -> t.type().equals("collection") && t.href().equals("/c/denim-shop")));
        assertTrue(r.terms().stream().anyMatch(t -> t.href().equals("/c/women?category=skirts")));
    }
}
