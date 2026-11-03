package com.otterworks.ottershops.bag;

import com.otterworks.ottershops.auth.CurrentCustomer;
import com.otterworks.ottershops.pricing.FeeCalculator;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/bags")
public class BagController {
    private final BagService bags;
    private final CurrentCustomer current;

    public BagController(BagService bags, CurrentCustomer current) {
        this.bags = bags;
        this.current = current;
    }

    public record AddItem(String sku, Integer quantity) {}
    public record SetQuantity(int quantity) {}
    public record ApplyPromo(String code) {}

    public record BagView(UUID id, List<PricedBag.Line> items, int itemCount, int listSubtotalCents,
                          int subtotalCents, int discountCents, int merchandiseCents, String promoCode,
                          String promoDescription, String promoError, int freeShippingThresholdCents,
                          int freeShippingRemainingCents) {
        static BagView of(UUID id, PricedBag b) {
            int remaining = Math.max(0, FeeCalculator.FREE_SHIPPING_THRESHOLD_CENTS - b.merchandiseCents());
            return new BagView(id, b.lines(), b.itemCount(), b.listSubtotalCents(), b.subtotalCents(),
                    b.discountCents(), b.merchandiseCents(), b.promoCode(), b.promoDescription(), b.promoError(),
                    FeeCalculator.FREE_SHIPPING_THRESHOLD_CENTS, b.lines().isEmpty() ? 0 : remaining);
        }
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public BagView create(HttpServletRequest req) {
        UUID customer = current.id(req).orElse(null);
        UUID id = bags.create(customer);
        return BagView.of(id, bags.view(id, customer));
    }

    @GetMapping("/{id}")
    public BagView get(@PathVariable UUID id, HttpServletRequest req) {
        return BagView.of(id, bags.view(id, current.id(req).orElse(null)));
    }

    @PostMapping("/{id}/items")
    public BagView add(@PathVariable UUID id, @RequestBody AddItem body, HttpServletRequest req) {
        int qty = body.quantity() == null ? 1 : body.quantity();
        return BagView.of(id, bags.setQuantity(id, current.id(req).orElse(null), body.sku(), Math.max(1, qty), true));
    }

    @PatchMapping("/{id}/items/{sku}")
    public BagView update(@PathVariable UUID id, @PathVariable String sku, @RequestBody SetQuantity body, HttpServletRequest req) {
        return BagView.of(id, bags.setQuantity(id, current.id(req).orElse(null), sku, body.quantity(), false));
    }

    @DeleteMapping("/{id}/items/{sku}")
    public BagView remove(@PathVariable UUID id, @PathVariable String sku, HttpServletRequest req) {
        return BagView.of(id, bags.removeItem(id, current.id(req).orElse(null), sku));
    }

    @PostMapping("/{id}/promo")
    public BagView applyPromo(@PathVariable UUID id, @RequestBody ApplyPromo body, HttpServletRequest req) {
        return BagView.of(id, bags.applyPromo(id, current.id(req).orElse(null), body.code()));
    }

    @DeleteMapping("/{id}/promo")
    public BagView removePromo(@PathVariable UUID id, HttpServletRequest req) {
        return BagView.of(id, bags.removePromo(id, current.id(req).orElse(null)));
    }
}
