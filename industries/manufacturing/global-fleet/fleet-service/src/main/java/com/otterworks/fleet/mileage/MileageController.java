package com.otterworks.fleet.mileage;

import com.otterworks.fleet.config.CountryProfile;
import com.otterworks.fleet.domain.MileageClaim;
import java.math.BigDecimal;
import java.time.DateTimeException;
import java.time.YearMonth;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/mileage")
public class MileageController {

    private final MileageClaimService service;
    private final CountryProfile profile;

    public MileageController(MileageClaimService service, CountryProfile profile) {
        this.service = service;
        this.profile = profile;
    }

    @GetMapping("/quote")
    public MileageQuoteView quote(@RequestParam("distance") BigDecimal distance) {
        return service.quote(distance);
    }

    @PostMapping("/claims")
    @ResponseStatus(HttpStatus.CREATED)
    public ClaimView submit(@RequestBody MileageClaimRequest request) {
        MileageClaim claim = service.submit(
                request.employeeNo(),
                request.journeyDate(),
                request.distance(),
                request.purpose());
        return view(claim);
    }

    @GetMapping("/claims/pending")
    public List<ClaimView> pending() {
        return service.pending().stream().map(this::view).toList();
    }

    @PostMapping("/claims/{id}/approve")
    public ClaimView approve(@PathVariable Long id) {
        return view(service.approve(id));
    }

    @PostMapping("/claims/{id}/reject")
    public ClaimView reject(@PathVariable Long id) {
        return view(service.reject(id));
    }

    @GetMapping("/employees/{employeeNo}/claims")
    public MileageHistoryView history(@PathVariable String employeeNo) {
        return service.history(employeeNo);
    }

    @GetMapping("/employees/{employeeNo}/reimbursement")
    public MileageReimbursementView reimbursement(
            @PathVariable String employeeNo,
            @RequestParam String period) {
        return service.reimbursement(employeeNo, parsePeriod(period));
    }

    private ClaimView view(MileageClaim claim) {
        return ClaimView.from(claim, profile.distanceUnit().name(), profile.currency().getCurrencyCode());
    }

    private YearMonth parsePeriod(String period) {
        if (period == null || !period.matches("[0-9]{6}")) {
            throw new MileageException(MileageReason.INVALID_PERIOD);
        }
        try {
            return YearMonth.of(
                    Integer.parseInt(period.substring(0, 4)),
                    Integer.parseInt(period.substring(4, 6)));
        } catch (DateTimeException | NumberFormatException exception) {
            throw new MileageException(MileageReason.INVALID_PERIOD);
        }
    }
}
