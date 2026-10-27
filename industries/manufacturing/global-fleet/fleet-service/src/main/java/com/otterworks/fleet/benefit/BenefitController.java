package com.otterworks.fleet.benefit;

import com.otterworks.fleet.config.CountryProfile;
import com.otterworks.fleet.eligibility.BelowGradeHolder;
import com.otterworks.fleet.eligibility.EligibilityService;
import jakarta.validation.Valid;
import java.time.Clock;
import java.time.YearMonth;
import java.util.List;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/benefit")
public class BenefitController {

    private final BenefitPeriodService benefitPeriodService;
    private final EligibilityService eligibilityService;
    private final Clock clock;

    public BenefitController(
            BenefitPeriodService benefitPeriodService,
            EligibilityService eligibilityService,
            ObjectProvider<Clock> clockProvider) {
        this.benefitPeriodService = benefitPeriodService;
        this.eligibilityService = eligibilityService;
        this.clock = clockProvider.getIfAvailable(Clock::systemUTC);
    }

    @GetMapping("/employees/{employeeNo}")
    public BenefitInquiryView inquiry(
            @PathVariable String employeeNo,
            @RequestParam(name = "period", required = false) String period) {
        YearMonth month = period == null
                ? YearMonth.now(clock)
                : BenefitPeriodService.parsePeriod(period);
        return benefitPeriodService.inquiry(employeeNo, month);
    }

    @GetMapping("/employees/{employeeNo}/statement")
    public BenefitStatementView statement(
            @PathVariable String employeeNo,
            @RequestParam(name = "period", required = false) String period) {
        YearMonth month = period == null
                ? YearMonth.now(clock)
                : BenefitPeriodService.parsePeriod(period);
        return benefitPeriodService.statement(employeeNo, month);
    }

    @GetMapping("/periods")
    public List<BenefitPeriodView> periods() {
        return benefitPeriodService.list();
    }

    @PostMapping("/periods")
    public ResponseEntity<BenefitPeriodView> open(@Valid @RequestBody OpenBenefitPeriodRequest request) {
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(benefitPeriodService.open(BenefitPeriodService.parsePeriod(request.period())));
    }

    @PostMapping("/periods/{period}/close")
    public BenefitPeriodView close(@PathVariable String period) {
        return benefitPeriodService.close(BenefitPeriodService.parsePeriod(period));
    }

    @GetMapping("/periods/{period}/results")
    public List<BenefitInquiryView> results(@PathVariable String period) {
        return benefitPeriodService.results(BenefitPeriodService.parsePeriod(period));
    }

    @GetMapping("/periods/{period}/payroll-file")
    public ResponseEntity<byte[]> payrollFile(@PathVariable String period) {
        BenefitPayrollFile file = benefitPeriodService.payrollFile(BenefitPeriodService.parsePeriod(period));
        return ResponseEntity.ok()
                .contentType(MediaType.APPLICATION_OCTET_STREAM)
                .header(HttpHeaders.CONTENT_DISPOSITION, ContentDisposition.attachment()
                        .filename("BENOUT-" + period + ".dat")
                        .build()
                        .toString())
                .body(file.getContent());
    }

    @GetMapping("/periods/{period}/below-grade-holders")
    public List<BelowGradeHolder> belowGradeHolders(@PathVariable String period) {
        return eligibilityService.belowGradeHolders(BenefitPeriodService.parsePeriod(period));
    }
}
