package com.otterworks.ottershops.pricing;

public enum ShippingMethod {
    STANDARD("Standard (5-7 business days)", 7),
    EXPRESS("Express (2 business days)", 2);

    private final String label;
    private final int businessDays;

    ShippingMethod(String label, int businessDays) {
        this.label = label;
        this.businessDays = businessDays;
    }

    public String label() { return label; }
    public int businessDays() { return businessDays; }
}
