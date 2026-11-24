package com.otterworks.rating.service;

import com.otterworks.rating.config.RatingProperties;
import com.otterworks.rating.model.Policy;
import com.otterworks.rating.model.Quote;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.Optional;
import java.util.Set;
import org.springframework.stereotype.Service;

/** Rates a policy for both the nightly batch and the online quote page. */
@Service
public class RatingService {

    private static final Set<String> LINES = Set.of("GL", "PR", "CA");
    private static final BigDecimal MAX_SCHEDULE = new BigDecimal("0.25");
    private static final BigDecimal ENDORSEMENT_CAP = new BigDecimal("0.25");

    private final RatingTables tables;
    private final BigDecimal policyFee;

    public RatingService(RatingTables tables, RatingProperties properties) {
        this.tables = tables;
        this.policyFee = properties.policyFee();
    }

    public Quote rate(Policy p) {
        if (!LINES.contains(p.line())) {
            return Quote.refused(p.id(), "REJ", "LN");
        }
        if (p.exposure().signum() <= 0) {
            return Quote.refused(p.id(), "REJ", "EX");
        }
        Optional<RatingTables.Eligibility> eligibility = tables.eligibility(p.line(), p.classCode(), p.state());
        if (eligibility.isPresent() && !eligibility.get().eligible()) {
            return Quote.refused(p.id(), "DEC", eligibility.get().reason());
        }
        Optional<RatingTables.ClassRate> classRate = tables.classRate(p.line(), p.classCode(), p.effective());
        if (classRate.isEmpty()) {
            return Quote.refused(p.id(), "REJ", "CL");
        }

        String source = "T";
        Optional<RatingTables.TerritoryFactor> territory =
                tables.territory(p.line(), p.territory(), p.effective());
        if (territory.isEmpty()) {
            territory = tables.territory(p.line(), RatingTables.DEFAULT_TERRITORY, p.effective());
            source = "D";
        }
        if (territory.isEmpty()) {
            return Quote.refused(p.id(), "REJ", "TR");
        }
        BigDecimal factor = territory.get().factor();
        Optional<RatingTables.Override> override = tables.override(p.line(), p.classCode(), p.territory(), p.effective());
        if (override.isPresent()) {
            factor = override.get().factor();
            source = "O";
        }

        BigDecimal base = applyFactor(applyFactor(p.exposure(), classRate.get().rate()), factor);
        BigDecimal premium = applyFactor(base, experienceMod(p));
        premium = applyFactor(premium, deductibleCredit(p));
        premium = applyFactor(premium, BigDecimal.ONE.add(scheduleMod(p)));
        premium = applyFactor(premium, multiPolicyCredit(p));
        premium = applyFactor(premium, windSurcharge(p));

        boolean minimumApplied = false;
        Optional<RatingTables.Minimum> minimum = tables.minimum(p.line(), p.state());
        if (minimum.isPresent() && premium.compareTo(minimum.get().minimum()) < 0) {
            premium = money(minimum.get().minimum());
            minimumApplied = true;
        }

        BigDecimal endorsements = endorsements(p, premium);
        return new Quote(p.id(), "OK", "", base, premium, minimumApplied, endorsements,
                money(policyFee), premium.add(endorsements).add(policyFee), source);
    }

    BigDecimal experienceMod(Policy p) {
        if (p.claims() >= 3) {
            return new BigDecimal("1.25");
        }
        if (p.claims() == 0 && p.yearsInBusiness() >= 3) {
            return new BigDecimal("0.90");
        }
        return BigDecimal.ONE;
    }

    BigDecimal deductibleCredit(Policy p) {
        if (!p.line().equals("PR") && !p.line().equals("CA")) {
            return BigDecimal.ONE;
        }
        if (p.deductible() >= 5000) {
            return new BigDecimal("0.92");
        }
        if (p.deductible() >= 2500) {
            return new BigDecimal("0.95");
        }
        if (p.deductible() >= 1000) {
            return new BigDecimal("0.98");
        }
        return BigDecimal.ONE;
    }

    BigDecimal scheduleMod(Policy p) {
        return p.scheduleMod().max(MAX_SCHEDULE.negate()).min(MAX_SCHEDULE);
    }

    BigDecimal multiPolicyCredit(Policy p) {
        boolean packageLine = p.line().equals("GL") || p.line().equals("PR");
        return p.multiPolicy() && packageLine ? new BigDecimal("0.95") : BigDecimal.ONE;
    }

    BigDecimal windSurcharge(Policy p) {
        if (!p.line().equals("PR") || !p.state().equals("FL")) {
            return BigDecimal.ONE;
        }
        return tables.surcharge("PR", "WND").map(RatingTables.TerritoryFactor::factor).orElse(BigDecimal.ONE);
    }

    /** Endorsements are quoted in whole dollars and capped at a quarter of the premium. */
    BigDecimal endorsements(Policy p, BigDecimal premium) {
        BigDecimal total = BigDecimal.ZERO;
        if (p.line().equals("GL")) {
            total = total.add(BigDecimal.valueOf(50L * Math.clamp(p.additionalInsureds(), 0, 3)));
        }
        if (p.equipment() && p.line().equals("PR")) {
            total = total.add(dollars(applyFactor(premium, new BigDecimal("0.03")).max(new BigDecimal("75"))));
        }
        if (p.waiver() && (p.line().equals("GL") || p.line().equals("CA"))) {
            total = total.add(dollars(applyFactor(premium, new BigDecimal("0.02"))));
        }
        if (p.hiredNonOwned() && p.line().equals("GL")) {
            total = total.add(new BigDecimal("120"));
        }
        return total.min(applyFactor(premium, ENDORSEMENT_CAP)).setScale(2);
    }

    private static BigDecimal applyFactor(BigDecimal amount, BigDecimal factor) {
        return amount.multiply(factor).setScale(2, RoundingMode.HALF_UP);
    }

    private static BigDecimal money(BigDecimal amount) {
        return amount.setScale(2, RoundingMode.HALF_EVEN);
    }

    private static BigDecimal dollars(BigDecimal amount) {
        return amount.setScale(0, RoundingMode.HALF_UP);
    }
}
