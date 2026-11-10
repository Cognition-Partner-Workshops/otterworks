package com.otterworks.commission.calculation;

import java.math.BigDecimal;
import java.util.LinkedHashMap;
import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import com.otterworks.commission.common.OraException;
import com.otterworks.commission.common.OracleText;

/**
 * Delegate target of COMMISSION_PKG.calculate_policy_commission. The path
 * carries TO_CHAR(p_policy_id), or "null" when the caller passed NULL.
 */
@RestController
public class CalculationController {

    private static final Logger log = LoggerFactory.getLogger(CalculationController.class);

    public record CalculationRequest(String period_month, String actor) {
    }

    private final CalculationService service;

    public CalculationController(CalculationService service) {
        this.service = service;
    }

    @PostMapping("/policies/{policyId}/commission")
    public Map<String, Object> calculate(@PathVariable String policyId, @RequestBody CalculationRequest req) {
        log.info("POST /policies/{}/commission period_month={}", policyId, req.period_month());
        String policyText = "null".equals(policyId) ? "" : policyId;
        BigDecimal id = policyText.isEmpty() ? null : parsePolicyId(policyText);
        CalculationService.Result r = service.calculate(id, policyText, req.period_month(), req.actor());
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("policy_id", id);
        body.put("period_month", req.period_month());
        body.put("rows", r.rows());
        return body;
    }

    private static BigDecimal parsePolicyId(String text) {
        try {
            return OracleText.parseNumber(text);
        } catch (NumberFormatException e) {
            throw new OraException(-20000, "Malformed policy id: " + text);
        }
    }
}
