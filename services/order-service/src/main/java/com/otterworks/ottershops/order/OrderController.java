package com.otterworks.ottershops.order;

import com.otterworks.ottershops.auth.Customer;
import com.otterworks.ottershops.auth.CurrentCustomer;
import com.otterworks.ottershops.common.ApiException;
import com.otterworks.ottershops.common.Money;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.util.HtmlUtils;

import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

@RestController
@RequestMapping("/api")
public class OrderController {
    private static final DateTimeFormatter DATE = DateTimeFormatter.ofPattern("MMM d, yyyy").withZone(ZoneId.of("America/Los_Angeles"));
    private final OrderRepository orders;
    private final CurrentCustomer current;
    private final ReturnService returns;

    public OrderController(OrderRepository orders, CurrentCustomer current, ReturnService returns) {
        this.orders = orders;
        this.current = current;
        this.returns = returns;
    }

    /** The owner sees their order when signed in; anyone else needs the order number and the order email. */
    OrderView authorized(String number, String email, HttpServletRequest req) {
        OrderView order = orders.findByNumber(number).orElseThrow(() -> ApiException.notFound("Order"));
        Optional<UUID> me = current.id(req);
        boolean owner = me.isPresent() && orders.ownerOf(order.orderNumber()).filter(me.get()::equals).isPresent();
        boolean emailMatches = email != null && email.trim().equalsIgnoreCase(order.email());
        if (!owner && !emailMatches) throw ApiException.notFound("Order");
        return order;
    }

    @GetMapping("/orders/lookup")
    public OrderView lookup(@RequestParam String number, @RequestParam String email, HttpServletRequest req) {
        if (number.isBlank() || email.isBlank()) {
            throw ApiException.badRequest("LOOKUP_INVALID", "Enter your order number and email");
        }
        try {
            return authorized(number, email, req);
        } catch (ApiException e) {
            throw new ApiException(e.status(), "ORDER_NOT_FOUND", "We couldn't find an order with that number and email");
        }
    }

    @GetMapping("/orders/{number}")
    public OrderView get(@PathVariable String number, @RequestParam(required = false) String email, HttpServletRequest req) {
        return authorized(number, email, req);
    }

    @GetMapping(value = "/orders/{number}/invoice", produces = MediaType.TEXT_HTML_VALUE)
    public ResponseEntity<String> invoice(@PathVariable String number, @RequestParam(required = false) String email,
                                          HttpServletRequest req) {
        OrderView o = authorized(number, email, req);
        StringBuilder rows = new StringBuilder();
        for (OrderView.Line l : o.lines()) {
            rows.append("<tr><td>").append(h(l.name())).append("<br><small>").append(h(l.color())).append(" / ")
                    .append(h(l.size())).append(" &middot; ").append(h(l.sku())).append("</small></td><td>")
                    .append(l.quantity()).append("</td><td>").append(Money.format(l.unitPriceCents()))
                    .append("</td><td>").append(l.discountCents() > 0 ? "-" + Money.format(l.discountCents()) : "")
                    .append("</td><td>").append(Money.format(l.lineTotalCents())).append("</td></tr>");
        }
        StringBuilder totals = new StringBuilder();
        totals.append(row("Subtotal", Money.format(o.subtotalCents())));
        if (o.discountCents() > 0) totals.append(row("Promo " + h(o.promoCode()), "-" + Money.format(o.discountCents())));
        totals.append(row("Shipping", o.shippingCents() == 0 ? "Free" : Money.format(o.shippingCents())));
        o.fees().forEach(f -> totals.append(row(h(f.label()), Money.format(f.amountCents()))));
        totals.append(row("Tax (" + o.taxRate().stripTrailingZeros().toPlainString() + "%)", Money.format(o.taxCents())));
        totals.append(row("<strong>Total</strong>", "<strong>" + Money.format(o.totalCents()) + "</strong>"));
        String fulfil = o.pickup() != null
                ? "Pickup at " + h(o.pickup().storeName()) + ", " + h(o.pickup().address()) + ", " + h(o.pickup().city()) + ", " + h(o.pickup().state())
                : "Ship to " + h(o.shipTo().name()) + ", " + h(o.shipTo().line1()) + ", " + h(o.shipTo().city()) + ", "
                + h(o.shipTo().state()) + " " + h(o.shipTo().zip()) + " (" + h(o.shippingMethod()) + ")";
        String html = """
                <!doctype html><html><head><meta charset="utf-8"><title>Invoice %s</title>
                <style>body{font-family:system-ui,sans-serif;max-width:760px;margin:40px auto;color:#1b2a3a}
                table{width:100%%;border-collapse:collapse}td,th{padding:8px;border-bottom:1px solid #e3e7ec;text-align:left}
                .totals td:last-child{text-align:right}h1{color:#0b3c5d}small{color:#5b6b7b}</style></head><body>
                <h1>OtterShops</h1><p><strong>Invoice %s</strong><br>Order %s &middot; %s<br>%s</p><p>%s</p>
                <table><tr><th>Item</th><th>Qty</th><th>Price</th><th>Promo</th><th>Total</th></tr>%s</table>
                <table class="totals">%s</table><p>Paid with %s ending %s.</p>
                <p><small>OtterShops is a fictional store built for demos. No goods will ship.</small></p>
                <script>if(location.search.includes('print=1'))window.print()</script></body></html>
                """.formatted(h(o.invoiceNumber()), h(o.invoiceNumber()), h(o.orderNumber()), DATE.format(o.createdAt()),
                h(o.email()), fulfil, rows, totals, h(o.cardBrand()), h(o.cardLast4()));
        return ResponseEntity.ok().contentType(MediaType.TEXT_HTML).body(html);
    }

    @PostMapping("/orders/{number}/returns")
    @ResponseStatus(HttpStatus.CREATED)
    public OrderView.ReturnView startReturn(@PathVariable String number, @RequestBody ReturnService.Request body,
                                            HttpServletRequest req) {
        return returns.create(authorized(number, body.email(), req), body);
    }

    @GetMapping("/returns/reasons")
    public List<String> returnReasons() {
        return ReturnService.REASONS.stream().sorted().toList();
    }

    @GetMapping("/account")
    public Map<String, Object> account(HttpServletRequest req) {
        Customer c = current.get(req).orElseThrow(ApiException::unauthorized);
        List<OrderView.Summary> history = orders.forCustomer(c.id());
        return Map.of("customer", c, "orders", history);
    }

    @GetMapping("/account/orders")
    public List<OrderView.Summary> history(HttpServletRequest req) {
        Customer c = current.get(req).orElseThrow(ApiException::unauthorized);
        return orders.forCustomer(c.id());
    }

    private static String row(String label, String value) {
        return "<tr><td>" + label + "</td><td>" + value + "</td></tr>";
    }

    private static String h(String s) {
        return s == null ? "" : HtmlUtils.htmlEscape(s);
    }
}
