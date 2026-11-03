package com.otterworks.ottershops.engage;

import com.otterworks.ottershops.auth.Customer;
import com.otterworks.ottershops.catalog.CatalogService;
import com.otterworks.ottershops.catalog.Product;
import com.otterworks.ottershops.common.ApiException;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

@Service
public class ReviewService {
    public static final Set<String> FIT_NOTES = Set.of("Runs small", "True to size", "Runs large");
    static final Map<String, String> SORTS = Map.of(
            "recent", "created_at DESC, id DESC",
            "helpful", "helpful_count DESC, created_at DESC, id DESC",
            "highest", "rating DESC, created_at DESC, id DESC",
            "lowest", "rating ASC, created_at DESC, id DESC");

    private final JdbcTemplate jdbc;
    private final CatalogService catalog;

    public ReviewService(JdbcTemplate jdbc, CatalogService catalog) {
        this.jdbc = jdbc;
        this.catalog = catalog;
    }

    public record Review(long id, String author, String location, int rating, String title, String body,
                         String fitNote, String sizePurchased, boolean verified, int helpfulCount, Instant createdAt) {}

    public record FitSummary(int runsSmall, int trueToSize, int runsLarge, String verdict) {}

    public record Summary(double rating, int ratingCount, int writtenCount, Map<Integer, Integer> histogram,
                          FitSummary fit) {}

    public record Page(Summary summary, List<Review> reviews, int total, int page, int pageSize, String sort,
                       Integer rating) {}

    public record NewReview(Integer rating, String title, String body, String fitNote, String sizePurchased,
                            String author, String location) {}

    public Page list(String productId, String sort, Integer rating, int page, int pageSize) {
        Product p = catalog.product(productId);
        String order = SORTS.getOrDefault(sort == null ? "helpful" : sort, SORTS.get("helpful"));
        String sortKey = SORTS.containsKey(sort) ? sort : "helpful";
        if (rating != null && (rating < 1 || rating > 5)) throw ApiException.badRequest("RATING_INVALID", "Rating filter must be 1-5");
        int size = Math.max(1, Math.min(pageSize, 20));
        int pg = Math.max(1, page);
        String where = "product_id = ?" + (rating == null ? "" : " AND rating = ?");
        Object[] args = rating == null ? new Object[]{productId} : new Object[]{productId, rating};
        Integer total = jdbc.queryForObject("SELECT count(*) FROM reviews WHERE " + where, Integer.class, args);
        Object[] paged = rating == null ? new Object[]{productId, size, (pg - 1) * size}
                : new Object[]{productId, rating, size, (pg - 1) * size};
        List<Review> rows = jdbc.query("""
                SELECT id, author, location, rating, title, body, fit_note, size_purchased, verified, helpful_count, created_at
                FROM reviews WHERE %s ORDER BY %s LIMIT ? OFFSET ?""".formatted(where, order), (rs, i) -> new Review(
                rs.getLong(1), rs.getString(2), rs.getString(3), rs.getInt(4), rs.getString(5), rs.getString(6),
                rs.getString(7), rs.getString(8), rs.getBoolean(9), rs.getInt(10), rs.getTimestamp(11).toInstant()), paged);
        return new Page(summary(p), rows, total == null ? 0 : total, pg, size, sortKey, rating);
    }

    Summary summary(Product p) {
        Map<Integer, Integer> histogram = new LinkedHashMap<>();
        for (int s = 5; s >= 1; s--) histogram.put(s, 0);
        jdbc.query("SELECT rating, count(*) FROM reviews WHERE product_id = ? GROUP BY rating",
                rs -> { histogram.put(rs.getInt(1), rs.getInt(2)); }, p.id());
        int[] fit = new int[3];
        jdbc.query("SELECT fit_note, count(*) FROM reviews WHERE product_id = ? AND fit_note IS NOT NULL GROUP BY fit_note", rs -> {
            switch (rs.getString(1)) {
                case "Runs small" -> fit[0] = rs.getInt(2);
                case "True to size" -> fit[1] = rs.getInt(2);
                case "Runs large" -> fit[2] = rs.getInt(2);
                default -> { }
            }
        }, p.id());
        int written = histogram.values().stream().mapToInt(Integer::intValue).sum();
        return new Summary(p.rating(), p.reviewCount(), written, histogram, new FitSummary(fit[0], fit[1], fit[2], verdict(fit)));
    }

    static String verdict(int[] fit) {
        int total = fit[0] + fit[1] + fit[2];
        if (total == 0) return null;
        if (fit[0] * 2 > total) return "Runs small: consider sizing up";
        if (fit[2] * 2 > total) return "Runs large: consider sizing down";
        return "Fits true to size";
    }

    /** Folds a new rating into the product's running average. */
    static double foldRating(double rating, int count, int newRating) {
        return BigDecimal.valueOf((rating * count + newRating) / (count + 1.0)).setScale(1, RoundingMode.HALF_UP).doubleValue();
    }

    @Transactional
    public Review create(String productId, NewReview in, Customer customer) {
        Product p = catalog.product(productId);
        if (in.rating() == null || in.rating() < 1 || in.rating() > 5) {
            throw ApiException.badRequest("RATING_INVALID", "Choose a star rating from 1 to 5");
        }
        String title = trim(in.title(), 120);
        String body = trim(in.body(), 2000);
        if (body == null || body.length() < 10) {
            throw ApiException.badRequest("REVIEW_TOO_SHORT", "Tell other shoppers a little more (at least 10 characters)");
        }
        String fit = in.fitNote() == null || in.fitNote().isBlank() ? null : in.fitNote();
        if (fit != null && !FIT_NOTES.contains(fit)) throw ApiException.badRequest("FIT_INVALID", "Unknown fit option");
        String size = trim(in.sizePurchased(), 20);
        if (size != null && !p.skus().stream().map(s -> s.size()).toList().contains(size)) {
            throw ApiException.badRequest("SIZE_INVALID", "That size isn't offered for this item");
        }
        String author = customer != null ? displayName(customer) : trim(in.author(), 40);
        if (author == null || author.isBlank()) throw ApiException.badRequest("AUTHOR_REQUIRED", "Add a display name");
        boolean verified = customer != null && Boolean.TRUE.equals(jdbc.queryForObject("""
                SELECT EXISTS (SELECT 1 FROM orders o JOIN order_lines l ON l.order_id = o.id
                               WHERE o.customer_id = ? AND l.product_id = ?)""", Boolean.class, customer.id(), productId));
        Instant now = Instant.now();
        Long id = jdbc.queryForObject("""
                INSERT INTO reviews (product_id, author, location, rating, title, body, fit_note, size_purchased, verified,
                                     helpful_count, customer_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?) RETURNING id""", Long.class,
                productId, author, trim(in.location(), 60), in.rating(), title, body, fit, size, verified,
                customer == null ? null : customer.id(), Timestamp.from(now), Timestamp.from(now));
        jdbc.update("UPDATE products SET rating = ?, review_count = review_count + 1 WHERE id = ?",
                foldRating(p.rating(), p.reviewCount(), in.rating()), productId);
        catalog.refresh();
        return new Review(id == null ? 0 : id, author, trim(in.location(), 60), in.rating(), title, body, fit, size,
                verified, 0, now);
    }

    /** One helpful vote per review per voter (customer id or anonymous browser token). */
    @Transactional
    public int helpful(long reviewId, String voter) {
        if (voter == null || voter.isBlank() || voter.length() > 80) {
            throw ApiException.badRequest("VOTER_REQUIRED", "Missing voter token");
        }
        Integer exists = jdbc.queryForObject("SELECT count(*) FROM reviews WHERE id = ?", Integer.class, reviewId);
        if (exists == null || exists == 0) throw ApiException.notFound("Review");
        int inserted = jdbc.update("INSERT INTO review_votes (review_id, voter) VALUES (?, ?) ON CONFLICT DO NOTHING", reviewId, voter);
        if (inserted == 0) throw new ApiException(HttpStatus.CONFLICT, "ALREADY_VOTED", "You already marked this review helpful");
        return jdbc.queryForObject("UPDATE reviews SET helpful_count = helpful_count + 1, updated_at = now() WHERE id = ? RETURNING helpful_count",
                Integer.class, reviewId);
    }

    static String displayName(Customer c) {
        String last = c.lastName() == null || c.lastName().isBlank() ? "" : " " + c.lastName().charAt(0) + ".";
        return c.firstName() + last;
    }

    static String trim(String s, int max) {
        if (s == null) return null;
        String t = s.trim();
        if (t.isEmpty()) return null;
        return t.length() > max ? t.substring(0, max) : t;
    }
}
