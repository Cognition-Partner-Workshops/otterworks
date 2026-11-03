package com.otterworks.ottershops.engage;

import com.otterworks.ottershops.auth.CurrentCustomer;
import com.otterworks.ottershops.catalog.CatalogService;
import com.otterworks.ottershops.catalog.Product;
import com.otterworks.ottershops.catalog.SearchSuggestions;
import com.otterworks.ottershops.catalog.Sku;
import com.otterworks.ottershops.common.ApiException;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api")
public class EngageController {
    private final CatalogService catalog;
    private final CurrentCustomer current;
    private final ReviewService reviews;
    private final WishlistService wishlists;
    private final StockNotificationService notifications;
    private final GiftCardService giftCards;

    public EngageController(CatalogService catalog, CurrentCustomer current, ReviewService reviews,
                            WishlistService wishlists, StockNotificationService notifications, GiftCardService giftCards) {
        this.catalog = catalog;
        this.current = current;
        this.reviews = reviews;
        this.wishlists = wishlists;
        this.notifications = notifications;
        this.giftCards = giftCards;
    }

    public record NotifyRequest(String sku, String email) {}
    public record VoteRequest(String voter) {}
    public record VoteResult(long reviewId, int helpfulCount) {}
    public record WishItem(String color) {}
    public record Claim(UUID wishlistId) {}
    public record GiftCardRequest(String number, String pin) {}
    public record Availability(String sku, String productId, String color, String size, int onlineStock,
                               List<StoreAvailability.Result> stores) {}

    @GetMapping("/search/suggest")
    public SearchSuggestions.Result suggest(@RequestParam(defaultValue = "") String q) {
        return SearchSuggestions.suggest(q, catalog, 6);
    }

    @GetMapping("/products/{id}/reviews")
    public ReviewService.Page reviews(@PathVariable String id, @RequestParam(required = false) String sort,
                                      @RequestParam(required = false) Integer rating,
                                      @RequestParam(defaultValue = "1") int page,
                                      @RequestParam(defaultValue = "5") int pageSize) {
        return reviews.list(id, sort, rating, page, pageSize);
    }

    @PostMapping("/products/{id}/reviews")
    @ResponseStatus(HttpStatus.CREATED)
    public ReviewService.Review writeReview(@PathVariable String id, @RequestBody ReviewService.NewReview body,
                                            HttpServletRequest req) {
        return reviews.create(id, body, current.get(req).orElse(null));
    }

    @PostMapping("/reviews/{id}/helpful")
    public VoteResult helpful(@PathVariable long id, @RequestBody(required = false) VoteRequest body, HttpServletRequest req) {
        String voter = current.id(req).map(c -> "c:" + c).orElse(body == null || body.voter() == null ? null : "g:" + body.voter());
        return new VoteResult(id, reviews.helpful(id, voter));
    }

    @GetMapping("/products/{id}/availability")
    public Availability availability(@PathVariable String id, @RequestParam String sku,
                                     @RequestParam(defaultValue = "") String q) {
        Product p = catalog.product(id);
        Sku s = p.skus().stream().filter(x -> x.sku().equals(sku)).findFirst().orElseThrow(() -> ApiException.notFound("Item"));
        List<StoreAvailability.Result> stores = catalog.searchStores(q).stream().limit(6).map(st -> StoreAvailability.of(s, st)).toList();
        return new Availability(s.sku(), p.id(), s.color(), s.size(), s.stock(), stores);
    }

    @PostMapping("/stock-notifications")
    @ResponseStatus(HttpStatus.CREATED)
    public StockNotificationService.Subscription notifyMe(@RequestBody NotifyRequest body, HttpServletRequest req) {
        return notifications.subscribe(body.sku(), body.email(), current.id(req).orElse(null));
    }

    @PostMapping("/wishlists")
    @ResponseStatus(HttpStatus.CREATED)
    public WishlistService.View createWishlist(HttpServletRequest req) {
        return wishlists.create(current.id(req).orElse(null));
    }

    @GetMapping("/wishlists/{id}")
    public WishlistService.View wishlist(@PathVariable UUID id, HttpServletRequest req) {
        return wishlists.view(id, current.id(req).orElse(null));
    }

    @PutMapping("/wishlists/{id}/items/{productId}")
    public WishlistService.View addFavorite(@PathVariable UUID id, @PathVariable String productId,
                                            @RequestBody(required = false) WishItem body, HttpServletRequest req) {
        return wishlists.add(id, current.id(req).orElse(null), productId, body == null ? null : body.color());
    }

    @DeleteMapping("/wishlists/{id}/items/{productId}")
    public WishlistService.View removeFavorite(@PathVariable UUID id, @PathVariable String productId, HttpServletRequest req) {
        return wishlists.remove(id, current.id(req).orElse(null), productId);
    }

    @PostMapping("/wishlists/claim")
    public WishlistService.View claimWishlist(@RequestBody(required = false) Claim body, HttpServletRequest req) {
        return wishlists.claim(body == null ? null : body.wishlistId(), current.id(req).orElse(null));
    }

    @PostMapping("/gift-cards/balance")
    public GiftCardService.Balance giftCardBalance(@RequestBody GiftCardRequest body) {
        return giftCards.balance(body.number(), body.pin());
    }
}
