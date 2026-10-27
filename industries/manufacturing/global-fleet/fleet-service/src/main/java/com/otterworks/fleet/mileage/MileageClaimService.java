package com.otterworks.fleet.mileage;

import com.otterworks.fleet.assignment.CalendarMonthOpenPeriodLookup;
import com.otterworks.fleet.assignment.OpenPeriodLookup;
import com.otterworks.fleet.config.CountryProfile;
import com.otterworks.fleet.domain.AssignmentRepository;
import com.otterworks.fleet.domain.Assignment;
import com.otterworks.fleet.domain.BenefitPeriod;
import com.otterworks.fleet.domain.BenefitPeriodRepository;
import com.otterworks.fleet.domain.Employment;
import com.otterworks.fleet.domain.MileageClaim;
import com.otterworks.fleet.domain.MileageClaimRepository;
import com.otterworks.fleet.domain.MileageClaimStatus;
import com.otterworks.fleet.domain.Person;
import com.otterworks.fleet.domain.Vehicle;
import com.otterworks.fleet.eligibility.EligibilityService;
import java.math.BigDecimal;
import java.time.Clock;
import java.time.LocalDate;
import java.time.YearMonth;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Optional;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class MileageClaimService {

    private static final DateTimeFormatter PERIOD_FORMAT = DateTimeFormatter.ofPattern("yyyyMM");

    private final EligibilityService eligibilityService;
    private final CountryProfile profile;
    private final MileageClaimRepository claimRepository;
    private final AssignmentRepository assignmentRepository;
    private final BenefitPeriodRepository benefitPeriodRepository;
    private final Clock clock;
    private final OpenPeriodLookup openPeriodLookup;
    private final MileagePricing pricing;

    @Autowired
    public MileageClaimService(
            EligibilityService eligibilityService,
            CountryProfile profile,
            MileageClaimRepository claimRepository,
            AssignmentRepository assignmentRepository,
            BenefitPeriodRepository benefitPeriodRepository,
            ObjectProvider<Clock> clockProvider,
            ObjectProvider<OpenPeriodLookup> openPeriodLookupProvider,
            MileagePricing pricing) {
        this.eligibilityService = eligibilityService;
        this.profile = profile;
        this.claimRepository = claimRepository;
        this.assignmentRepository = assignmentRepository;
        this.benefitPeriodRepository = benefitPeriodRepository;
        this.clock = clockProvider.getIfAvailable(Clock::systemUTC);
        this.openPeriodLookup = openPeriodLookupProvider.getIfAvailable(
                () -> new CalendarMonthOpenPeriodLookup(clock));
        this.pricing = pricing;
    }

    public MileageClaimService(
            EligibilityService eligibilityService,
            CountryProfile profile,
            MileageClaimRepository claimRepository,
            AssignmentRepository assignmentRepository,
            BenefitPeriodRepository benefitPeriodRepository,
            Clock clock,
            OpenPeriodLookup openPeriodLookup,
            MileagePricing pricing) {
        this.eligibilityService = eligibilityService;
        this.profile = profile;
        this.claimRepository = claimRepository;
        this.assignmentRepository = assignmentRepository;
        this.benefitPeriodRepository = benefitPeriodRepository;
        this.clock = clock;
        this.openPeriodLookup = openPeriodLookup;
        this.pricing = pricing;
    }

    @Transactional(readOnly = true)
    public MileageQuoteView quote(BigDecimal distance) {
        int wholeDistance = validateDistance(distance);
        return new MileageQuoteView(
                wholeDistance,
                profile.distanceUnit().name(),
                profile.mileageRate(),
                pricing.quote(wholeDistance),
                profile.currency().getCurrencyCode());
    }

    @Transactional
    public MileageClaim submit(
            String employeeNo,
            LocalDate journeyDate,
            BigDecimal distance,
            String purpose) {
        int wholeDistance = validateDistance(distance);
        LocalDate claimDate = journeyDate == null ? today() : journeyDate;
        LocalDate today = today();
        if (claimDate.isAfter(today)) {
            throw new MileageException(MileageReason.JOURNEY_DATE_IN_FUTURE);
        }

        YearMonth paidMonth = paidMonth(claimDate, today);
        Employment employment = eligibilityService.requireMileageClaim(employeeNo, claimDate);
        Person person = employment.getPerson();
        Vehicle vehicle = vehicleOn(person.getId(), claimDate);
        BigDecimal rate = profile.mileageRate();
        String paidPeriod = PERIOD_FORMAT.format(paidMonth);
        Optional<BenefitPeriod> benefitPeriod = benefitPeriodRepository.findByPeriod(paidPeriod);

        return claimRepository.saveAndFlush(new MileageClaim(
                employment,
                benefitPeriod.orElse(null),
                vehicle,
                claimDate,
                wholeDistance,
                MileageClaimStatus.PENDING,
                rate,
                pricing.amount(wholeDistance, rate),
                paidPeriod,
                purpose == null ? "" : purpose,
                clock.instant()));
    }

    @Transactional
    public MileageClaim approve(Long id) {
        MileageClaim claim = pendingClaim(id);
        claim.approve(clock.instant());
        return claimRepository.saveAndFlush(claim);
    }

    @Transactional
    public MileageClaim reject(Long id) {
        MileageClaim claim = pendingClaim(id);
        claim.reject(clock.instant());
        return claimRepository.saveAndFlush(claim);
    }

    @Transactional(readOnly = true)
    public List<MileageClaim> pending() {
        return claimRepository.findByStatusOrderByClaimDateAscIdAsc(MileageClaimStatus.PENDING);
    }

    @Transactional(readOnly = true)
    public MileageHistoryView history(String employeeNo) {
        Person person = eligibilityService.requireInquiry(employeeNo);
        LocalDate to = today();
        LocalDate from = to.minusMonths(profile.claimHistoryMonths());
        List<Long> employmentIds = eligibilityService.employments(person).stream()
                .map(Employment::getId)
                .toList();
        List<MileageClaim> claims = employmentIds.isEmpty()
                ? List.of()
                : claimRepository.findByEmployment_IdInAndClaimDateBetweenOrderByClaimDateDescIdDesc(
                        employmentIds, from, to);
        return new MileageHistoryView(
                person.getEmployeeNo(),
                from,
                to,
                claims.stream().map(this::view).toList());
    }

    @Transactional(readOnly = true)
    public MileageReimbursementView reimbursement(String employeeNo, YearMonth paidPeriod) {
        Person person = eligibilityService.requireInquiry(employeeNo);
        List<Long> employmentIds = eligibilityService.employments(person).stream()
                .map(Employment::getId)
                .toList();
        List<MileageClaim> claims = employmentIds.isEmpty()
                ? List.of()
                : claimRepository.findByEmployment_IdInAndPaidPeriodAndStatus(
                        employmentIds, PERIOD_FORMAT.format(paidPeriod), MileageClaimStatus.APPROVED);
        long distance = claims.stream().mapToLong(MileageClaim::getDistance).sum();
        BigDecimal amount = claims.stream()
                .map(MileageClaim::getAmount)
                .reduce(BigDecimal.ZERO.setScale(2), BigDecimal::add);
        return new MileageReimbursementView(
                person.getEmployeeNo(),
                PERIOD_FORMAT.format(paidPeriod),
                claims.size(),
                distance,
                amount,
                profile.currency().getCurrencyCode());
    }

    public int validateDistance(BigDecimal distance) {
        if (distance == null) {
            throw new MileageException(MileageReason.DISTANCE_REQUIRED);
        }
        if (distance.stripTrailingZeros().scale() > 0) {
            throw new MileageException(MileageReason.DISTANCE_NOT_WHOLE);
        }
        if (distance.compareTo(BigDecimal.ONE) < 0
                || distance.compareTo(BigDecimal.valueOf(profile.maxClaimDistance())) > 0) {
            throw new MileageException(MileageReason.DISTANCE_OUT_OF_RANGE);
        }
        return distance.intValueExact();
    }

    private MileageClaim pendingClaim(Long id) {
        MileageClaim claim = claimRepository.findByIdForUpdate(id)
                .orElseThrow(() -> new MileageException(MileageReason.CLAIM_NOT_FOUND));
        if (claim.getStatus() != MileageClaimStatus.PENDING) {
            throw new MileageException(MileageReason.CLAIM_ALREADY_DECIDED);
        }
        return claim;
    }

    private YearMonth paidMonth(LocalDate claimDate, LocalDate today) {
        YearMonth currentMonth = YearMonth.from(today);
        YearMonth claimMonth = YearMonth.from(claimDate);
        if (openPeriodLookup.isOpen(claimDate)) {
            return claimMonth;
        }
        if (!claimMonth.isBefore(currentMonth.minusMonths(profile.claimLookbackMonths()))) {
            if (!openPeriodLookup.isOpen(today)) {
                throw new MileageException(MileageReason.NO_OPEN_CLAIM_PERIOD);
            }
            return currentMonth;
        }
        throw new MileageException(MileageReason.JOURNEY_DATE_OUTSIDE_CLAIM_WINDOW);
    }

    private Vehicle vehicleOn(Long personId, LocalDate journeyDate) {
        Assignment assignment = assignmentRepository.findHistoryByPersonId(personId).stream()
                .filter(item -> !item.getStartDate().isAfter(journeyDate))
                .filter(item -> item.getEndDate() == null || !item.getEndDate().isBefore(journeyDate))
                .findFirst()
                .orElse(null);
        return assignment == null ? null : assignment.getVehicle();
    }

    private ClaimView view(MileageClaim claim) {
        return ClaimView.from(
                claim,
                profile.distanceUnit().name(),
                profile.currency().getCurrencyCode());
    }

    private LocalDate today() {
        return LocalDate.now(clock);
    }

}
