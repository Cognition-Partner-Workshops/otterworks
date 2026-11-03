package com.otterworks.ottershops.checkout;

import com.otterworks.ottershops.order.OrderView;

import java.util.UUID;

public record CheckoutRequest(UUID bagId, String email, String fulfillment, String shippingMethod,
                              OrderView.Address address, String phone, String storeId, Card card) {

    public record Card(String number, Integer expMonth, Integer expYear, String cvc, String name) {
        @Override
        public String toString() {
            return "Card[redacted]";
        }
    }

    public record Quote(UUID bagId, String fulfillment, String shippingMethod, String shipState, String storeId) {}
}
