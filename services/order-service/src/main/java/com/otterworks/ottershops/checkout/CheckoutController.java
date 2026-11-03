package com.otterworks.ottershops.checkout;

import com.otterworks.ottershops.auth.CurrentCustomer;
import com.otterworks.ottershops.catalog.CatalogService;
import com.otterworks.ottershops.order.OrderView;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/checkout")
public class CheckoutController {
    private final CheckoutService checkout;
    private final CurrentCustomer current;
    private final CatalogService catalog;

    public CheckoutController(CheckoutService checkout, CurrentCustomer current, CatalogService catalog) {
        this.checkout = checkout;
        this.current = current;
        this.catalog = catalog;
    }

    @PostMapping("/quote")
    public CheckoutService.QuoteView quote(@RequestBody CheckoutRequest.Quote body, HttpServletRequest req) {
        return checkout.quote(body, current.id(req).orElse(null));
    }

    @PostMapping
    public ResponseEntity<OrderView> place(@RequestBody CheckoutRequest body, HttpServletRequest req) {
        OrderView order = checkout.place(body, current.id(req).orElse(null));
        catalog.refresh();
        return ResponseEntity.status(HttpStatus.CREATED).body(order);
    }
}
