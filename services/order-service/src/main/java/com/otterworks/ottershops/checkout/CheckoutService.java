package com.otterworks.ottershops.checkout;

import com.otterworks.ottershops.auth.CustomerRepository;
import com.otterworks.ottershops.bag.BagRepository;
import com.otterworks.ottershops.bag.BagService;
import com.otterworks.ottershops.bag.PricedBag;
import com.otterworks.ottershops.catalog.CatalogService;
import com.otterworks.ottershops.catalog.Store;
import com.otterworks.ottershops.common.ApiException;
import com.otterworks.ottershops.order.OrderRepository;
import com.otterworks.ottershops.order.OrderView;
import com.otterworks.ottershops.payment.PaymentProvider;
import com.otterworks.ottershops.payment.PaymentRequest;
import com.otterworks.ottershops.payment.PaymentResult;
import com.otterworks.ottershops.pricing.Fee;
import com.otterworks.ottershops.pricing.FeeCalculator;
import com.otterworks.ottershops.pricing.Fulfillment;
import com.otterworks.ottershops.pricing.ShippingMethod;
import com.otterworks.ottershops.pricing.Totals;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

@Service
public class CheckoutService {
    private static final Logger log = LoggerFactory.getLogger(CheckoutService.class);

    private final JdbcTemplate jdbc;
    private final BagRepository bagRepo;
    private final BagService bags;
    private final CatalogService catalog;
    private final FeeCalculator fees;
    private final PaymentProvider payments;
    private final OrderRepository orders;
    private final CustomerRepository customers;

    public CheckoutService(JdbcTemplate jdbc, BagRepository bagRepo, BagService bags, CatalogService catalog,
                           FeeCalculator fees, PaymentProvider payments, OrderRepository orders,
                           CustomerRepository customers) {
        this.jdbc = jdbc;
        this.bagRepo = bagRepo;
        this.bags = bags;
        this.catalog = catalog;
        this.fees = fees;
        this.payments = payments;
        this.orders = orders;
        this.customers = customers;
    }

    public record QuoteView(PricedBag bag, Totals totals, String fulfillment, String shippingMethod, Store store) {}

    public QuoteView quote(CheckoutRequest.Quote q, UUID customerId) {
        PricedBag bag = bags.view(q.bagId(), customerId);
        Fulfillment f = fulfillment(q.fulfillment());
        ShippingMethod m = method(q.shippingMethod());
        Store store = f == Fulfillment.PICKUP && q.storeId() != null ? catalog.store(q.storeId()) : null;
        Totals t = fees.totals(bag.subtotalCents(), bag.discountCents(), f, m, q.shipState(),
                store == null ? null : store.state());
        return new QuoteView(bag, t, f.name(), f == Fulfillment.SHIP ? m.name() : null, store);
    }

    /**
     * Places an order in one transaction: lock the bag and its SKU rows, reprice on the server, authorize the
     * card, then decrement stock and write the order. A decline or stock failure throws before any write, so
     * the transaction rolls back with stock untouched.
     */
    @Transactional
    public OrderView place(CheckoutRequest req, UUID customerId) {
        if (req.bagId() == null) throw ApiException.badRequest("BAG_REQUIRED", "Your bag is empty");
        String email = com.otterworks.ottershops.auth.AuthService.normalizeEmail(req.email());
        Fulfillment f = fulfillment(req.fulfillment());
        ShippingMethod m = method(req.shippingMethod());
        BagRepository.BagRow bagRow = bagRepo.find(req.bagId(), true).orElseThrow(() -> ApiException.notFound("Bag"));
        if (bagRow.customerId() != null && !bagRow.customerId().equals(customerId)) throw ApiException.notFound("Bag");
        if (!bagRow.open()) {
            throw new ApiException(HttpStatus.CONFLICT, "BAG_CLOSED", "This bag has already been checked out");
        }
        Map<String, Integer> items = bagRepo.items(req.bagId());
        if (items.isEmpty()) throw ApiException.badRequest("BAG_EMPTY", "Your bag is empty");

        Store store = null;
        OrderView.Address address = null;
        if (f == Fulfillment.PICKUP) {
            if (req.storeId() == null) throw ApiException.badRequest("STORE_REQUIRED", "Choose a pickup store");
            store = catalog.store(req.storeId());
            if (!store.pickupEnabled()) {
                throw ApiException.badRequest("PICKUP_UNAVAILABLE", store.name() + " isn't offering pickup right now");
            }
        } else {
            address = validAddress(req.address());
        }

        Map<String, Integer> locked = lockStock(items.keySet());
        List<Map<String, Object>> short_ = new ArrayList<>();
        items.forEach((sku, qty) -> {
            int available = locked.getOrDefault(sku, 0);
            if (qty > available) short_.add(Map.of("sku", sku, "requested", qty, "available", available));
        });
        if (!short_.isEmpty()) {
            throw new ApiException(HttpStatus.CONFLICT, "OUT_OF_STOCK",
                    "Some items in your bag sold out. Update your bag and try again.", Map.of("lines", short_));
        }

        PricedBag bag = bags.price(items, bagRow.promoCode(), locked);
        Totals totals = fees.totals(bag.subtotalCents(), bag.discountCents(), f, m,
                address == null ? null : address.state(), store == null ? null : store.state());

        CheckoutRequest.Card card = req.card();
        if (card == null || card.number() == null || card.expMonth() == null || card.expYear() == null) {
            throw ApiException.badRequest("CARD_INVALID", "Enter your card details");
        }
        PaymentResult payment = payments.authorize(new PaymentRequest(totals.totalCents(), "USD", card.number(),
                card.expMonth(), card.expYear(), card.cvc(), card.name(), req.bagId().toString()));
        if (payment.status() == PaymentResult.Status.DECLINED) {
            log.info("payment declined for bag {} ({} ending {})", req.bagId(), payment.cardBrand(), payment.last4());
            throw new ApiException(HttpStatus.PAYMENT_REQUIRED, "PAYMENT_DECLINED", payment.message());
        }
        if (!payment.approved()) {
            throw ApiException.badRequest("CARD_INVALID", payment.message());
        }

        items.forEach((sku, qty) -> jdbc.update("UPDATE skus SET stock = stock - ? WHERE sku = ?", qty, sku));

        UUID orderId = UUID.randomUUID();
        String number = orders.nextOrderNumber();
        orders.insertOrder(orderId, number, customerId, email, f.name(), f == Fulfillment.SHIP ? m.name() : null,
                store == null ? null : store.id(), address, trim(req.phone()), bag.promoCode(), totals.subtotalCents(),
                totals.discountCents(), totals.shippingCents(), totals.feesCents(), totals.taxCents(),
                totals.totalCents(), payments.name(), payment.reference(), payment.cardBrand(), payment.last4());
        int lineNo = 1;
        for (PricedBag.Line l : bag.lines()) {
            orders.insertLine(orderId, new OrderView.Line(lineNo++, l.sku(), l.productId(), l.name(), l.color(),
                    l.size(), l.image(), l.quantity(), l.unitListCents(), l.unitPriceCents(), l.discountCents(),
                    l.lineTotalCents()));
        }
        for (Fee fee : totals.fees()) orders.insertFee(orderId, fee);
        orders.insertInvoice(orders.nextInvoiceNumber(), orderId, totals.totalCents());
        bagRepo.markConverted(req.bagId());
        if (customerId != null) customers.addPoints(customerId, totals.totalCents() / 100);
        log.info("order {} placed: {} items, total {} cents, {}", number, bag.itemCount(), totals.totalCents(), f);
        return orders.findByNumber(number).orElseThrow();
    }

    private Map<String, Integer> lockStock(java.util.Set<String> skus) {
        Map<String, Integer> stock = new LinkedHashMap<>();
        List<String> sorted = skus.stream().sorted().toList();
        String placeholders = String.join(",", java.util.Collections.nCopies(sorted.size(), "?"));
        jdbc.query("SELECT sku, stock FROM skus WHERE sku IN (" + placeholders + ") ORDER BY sku FOR UPDATE",
                rs -> { stock.put(rs.getString(1), rs.getInt(2)); }, sorted.toArray());
        return stock;
    }

    private static OrderView.Address validAddress(OrderView.Address a) {
        if (a == null || blank(a.name()) || blank(a.line1()) || blank(a.city()) || blank(a.state()) || blank(a.zip())) {
            throw ApiException.badRequest("ADDRESS_INVALID", "Enter your full shipping address");
        }
        String state = a.state().trim().toUpperCase(Locale.ROOT);
        if (!state.matches("[A-Z]{2}")) throw ApiException.badRequest("ADDRESS_INVALID", "Use a two-letter state code");
        if (!a.zip().trim().matches("\\d{5}(-\\d{4})?")) throw ApiException.badRequest("ADDRESS_INVALID", "Enter a 5-digit ZIP code");
        return new OrderView.Address(a.name().trim(), a.line1().trim(), trim(a.line2()), a.city().trim(), state, a.zip().trim());
    }

    static Fulfillment fulfillment(String value) {
        try {
            return value == null ? Fulfillment.SHIP : Fulfillment.valueOf(value.trim().toUpperCase(Locale.ROOT));
        } catch (IllegalArgumentException e) {
            throw ApiException.badRequest("FULFILLMENT_INVALID", "Choose shipping or pickup");
        }
    }

    static ShippingMethod method(String value) {
        try {
            return value == null || value.isBlank() ? ShippingMethod.STANDARD
                    : ShippingMethod.valueOf(value.trim().toUpperCase(Locale.ROOT));
        } catch (IllegalArgumentException e) {
            throw ApiException.badRequest("SHIPPING_METHOD_INVALID", "Choose Standard or Express shipping");
        }
    }

    private static boolean blank(String s) {
        return s == null || s.isBlank();
    }

    private static String trim(String s) {
        return blank(s) ? null : s.trim();
    }
}
