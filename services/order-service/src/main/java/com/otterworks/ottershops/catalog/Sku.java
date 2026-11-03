package com.otterworks.ottershops.catalog;

public record Sku(String sku, String productId, String color, String colorHex, String colorFamily,
                  String size, int sizeOrder, int stock) {}
