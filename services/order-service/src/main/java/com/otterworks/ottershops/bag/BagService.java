package com.otterworks.ottershops.bag;

import com.otterworks.ottershops.catalog.CatalogService;
import com.otterworks.ottershops.catalog.Product;
import com.otterworks.ottershops.catalog.Sku;
import com.otterworks.ottershops.common.ApiException;
import com.otterworks.ottershops.pricing.CodeDiscount;
import com.otterworks.ottershops.pricing.PriceInfo;
import com.otterworks.ottershops.pricing.PricedLine;
import com.otterworks.ottershops.pricing.PricingService;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

@Service
public class BagService {
    public static final int MAX_PER_LINE = 10;

    private final BagRepository bags;
    private final CatalogService catalog;
    private final PricingService pricing;

    public BagService(BagRepository bags, CatalogService catalog, PricingService pricing) {
        this.bags = bags;
        this.catalog = catalog;
        this.pricing = pricing;
    }

    @Transactional
    public UUID create(UUID customerId) {
        if (customerId != null) {
            Optional<UUID> existing = bags.openBagFor(customerId);
            if (existing.isPresent()) return existing.get();
        }
        return bags.create(customerId);
    }

    public Optional<UUID> openBagFor(UUID customerId) {
        return bags.openBagFor(customerId);
    }

    /** A guest bag stays readable by anyone holding its id; a member's bag only by that member. */
    BagRepository.BagRow access(UUID bagId, UUID customerId, boolean forUpdate) {
        BagRepository.BagRow bag = bags.find(bagId, forUpdate).orElseThrow(() -> ApiException.notFound("Bag"));
        if (bag.customerId() != null && !bag.customerId().equals(customerId)) throw ApiException.notFound("Bag");
        if (!bag.open()) throw new ApiException(HttpStatus.GONE, "BAG_CLOSED", "This bag has already been checked out");
        return bag;
    }

    public PricedBag view(UUID bagId, UUID customerId) {
        BagRepository.BagRow bag = access(bagId, customerId, false);
        return price(bags.items(bagId), bag.promoCode(), null);
    }

    @Transactional
    public PricedBag setQuantity(UUID bagId, UUID customerId, String skuId, int quantity, boolean add) {
        BagRepository.BagRow bag = access(bagId, customerId, true);
        Sku sku = catalog.findSku(skuId).orElseThrow(() -> ApiException.notFound("Item"));
        Map<String, Integer> items = bags.items(bagId);
        int target = add ? items.getOrDefault(skuId, 0) + quantity : quantity;
        if (target <= 0) {
            bags.removeItem(bagId, skuId);
        } else {
            if (sku.stock() == 0) {
                throw new ApiException(HttpStatus.CONFLICT, "OUT_OF_STOCK", "This size is sold out");
            }
            if (target > sku.stock()) {
                throw new ApiException(HttpStatus.CONFLICT, "INSUFFICIENT_STOCK",
                        "Only " + sku.stock() + " left in this size", Map.of("available", sku.stock()));
            }
            if (target > MAX_PER_LINE) {
                throw ApiException.badRequest("QUANTITY_LIMIT", "You can buy up to " + MAX_PER_LINE + " of an item");
            }
            bags.setQuantity(bagId, skuId, target);
        }
        return price(bags.items(bagId), bag.promoCode(), null);
    }

    @Transactional
    public PricedBag removeItem(UUID bagId, UUID customerId, String sku) {
        BagRepository.BagRow bag = access(bagId, customerId, true);
        bags.removeItem(bagId, sku);
        return price(bags.items(bagId), bag.promoCode(), null);
    }

    @Transactional
    public PricedBag applyPromo(UUID bagId, UUID customerId, String code) {
        access(bagId, customerId, true);
        Map<String, Integer> items = bags.items(bagId);
        PricedBag plain = price(items, null, null);
        CodeDiscount discount = pricing.applyCode(code, pricedLines(plain));
        bags.setPromo(bagId, discount.code().code());
        return price(items, discount.code().code(), null);
    }

    @Transactional
    public PricedBag removePromo(UUID bagId, UUID customerId) {
        access(bagId, customerId, true);
        bags.setPromo(bagId, null);
        return price(bags.items(bagId), null, null);
    }

    public record SavedLine(String sku, String productId, String name, String color, String size, String image,
                            int unitPriceCents, int unitListCents, int stock) {}

    public List<SavedLine> saved(UUID bagId) {
        List<SavedLine> out = new ArrayList<>();
        for (String id : bags.saved(bagId)) {
            catalog.findSku(id).ifPresent(sku -> catalog.findProduct(sku.productId()).ifPresent(p -> {
                var price = catalog.price(p);
                out.add(new SavedLine(sku.sku(), p.id(), p.name(), sku.color(), sku.size(), catalog.imageFor(p, sku.color()),
                        price.priceCents(), price.listCents(), sku.stock()));
            }));
        }
        return out;
    }

    /** Moves a bag line to "saved for later"; it keeps no quantity and is not priced into the bag. */
    @Transactional
    public PricedBag saveForLater(UUID bagId, UUID customerId, String sku) {
        BagRepository.BagRow bag = access(bagId, customerId, true);
        Map<String, Integer> items = bags.items(bagId);
        if (!items.containsKey(sku)) throw ApiException.notFound("Bag item");
        bags.removeItem(bagId, sku);
        bags.save(bagId, sku);
        return price(bags.items(bagId), bag.promoCode(), null);
    }

    @Transactional
    public PricedBag moveToBag(UUID bagId, UUID customerId, String sku) {
        access(bagId, customerId, true);
        if (!bags.saved(bagId).contains(sku)) throw ApiException.notFound("Saved item");
        PricedBag priced = setQuantity(bagId, customerId, sku, 1, true);
        bags.unsave(bagId, sku);
        return priced;
    }

    @Transactional
    public PricedBag removeSaved(UUID bagId, UUID customerId, String sku) {
        BagRepository.BagRow bag = access(bagId, customerId, true);
        bags.unsave(bagId, sku);
        return price(bags.items(bagId), bag.promoCode(), null);
    }

    /**
     * Gives a signed-in shopper their guest bag. With no member bag the guest bag is adopted; otherwise
     * guest lines are merged into the member bag (quantities summed, capped at stock) and the guest bag closed.
     */
    @Transactional
    public UUID claim(UUID guestBagId, UUID customerId) {
        Optional<UUID> memberBag = bags.openBagFor(customerId);
        Optional<BagRepository.BagRow> guest = guestBagId == null ? Optional.empty()
                : bags.find(guestBagId, true).filter(b -> b.open() && b.customerId() == null);
        if (guest.isEmpty()) return memberBag.orElse(null);
        if (memberBag.isEmpty()) {
            bags.assignCustomer(guestBagId, customerId);
            return guestBagId;
        }
        UUID target = memberBag.get();
        Map<String, Integer> existing = bags.items(target);
        bags.items(guestBagId).forEach((sku, qty) -> {
            int stock = catalog.findSku(sku).map(Sku::stock).orElse(0);
            int merged = Math.min(Math.min(existing.getOrDefault(sku, 0) + qty, stock), MAX_PER_LINE);
            if (merged > 0) bags.setQuantity(target, sku, merged);
        });
        bags.saved(guestBagId).forEach(sku -> bags.save(target, sku));
        if (guest.get().promoCode() != null) bags.setPromo(target, guest.get().promoCode());
        bags.markConverted(guestBagId);
        return target;
    }

    /**
     * Prices items against the live catalog. {@code stockOverride} lets checkout price against rows it has
     * locked. A stored code that no longer qualifies is dropped from the totals and reported in promoError.
     */
    public PricedBag price(Map<String, Integer> items, String promoCode, Map<String, Integer> stockOverride) {
        List<PricedBag.Line> lines = new ArrayList<>();
        for (Map.Entry<String, Integer> e : items.entrySet()) {
            Optional<Sku> maybeSku = catalog.findSku(e.getKey());
            if (maybeSku.isEmpty()) continue;
            Sku sku = maybeSku.get();
            Product p = catalog.product(sku.productId());
            PriceInfo price = catalog.price(p);
            int qty = e.getValue();
            int stock = stockOverride != null ? stockOverride.getOrDefault(sku.sku(), 0) : sku.stock();
            lines.add(new PricedBag.Line(sku.sku(), p.id(), p.name(), sku.color(), sku.size(),
                    catalog.imageFor(p, sku.color()), qty, stock, price.listCents(), price.priceCents(),
                    price.priceCents() * qty, 0, price.priceCents() * qty, price.promoEligible(), price.excludedFromPromo()));
        }
        int listSubtotal = lines.stream().mapToInt(l -> l.unitListCents() * l.quantity()).sum();
        int subtotal = lines.stream().mapToInt(PricedBag.Line::lineSubtotalCents).sum();
        if (promoCode == null || lines.isEmpty()) {
            return new PricedBag(lines, listSubtotal, subtotal, 0, null, null, null);
        }
        try {
            CodeDiscount discount = pricing.applyCode(promoCode, pricedLines(lines));
            List<PricedBag.Line> discounted = lines.stream().map(l -> {
                int d = discount.perLine().getOrDefault(l.sku(), 0);
                return new PricedBag.Line(l.sku(), l.productId(), l.name(), l.color(), l.size(), l.image(), l.quantity(),
                        l.stock(), l.unitListCents(), l.unitPriceCents(), l.lineSubtotalCents(), d,
                        l.lineSubtotalCents() - d, l.promoEligible(), l.excludedFromPromo());
            }).toList();
            return new PricedBag(discounted, listSubtotal, subtotal, discount.totalCents(), discount.code().code(),
                    discount.code().description(), null);
        } catch (ApiException ex) {
            return new PricedBag(lines, listSubtotal, subtotal, 0, null, null, ex.getMessage());
        }
    }

    private static List<PricedLine> pricedLines(PricedBag bag) {
        return pricedLines(bag.lines());
    }

    private static List<PricedLine> pricedLines(List<PricedBag.Line> lines) {
        return lines.stream().map(l -> new PricedLine(l.sku(), l.lineSubtotalCents(), l.promoEligible())).toList();
    }
}
