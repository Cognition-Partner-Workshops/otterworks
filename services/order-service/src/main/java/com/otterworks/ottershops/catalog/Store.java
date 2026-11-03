package com.otterworks.ottershops.catalog;

public record Store(String id, String name, String address, String city, String state, String zip, String phone,
                    String hours, Double latitude, Double longitude, boolean pickupEnabled, int pickupReadyHours) {}
