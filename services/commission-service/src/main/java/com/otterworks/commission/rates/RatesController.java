package com.otterworks.commission.rates;

import java.util.Map;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.otterworks.commission.common.OracleText;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/** Endpoints the COMMISSION_PKG rates delegates call. */
@RestController
@RequestMapping("/rates")
public class RatesController {

    private static final Logger log = LoggerFactory.getLogger(RatesController.class);

    private final RatesService service;

    public RatesController(RatesService service) {
        this.service = service;
    }

    public record UpsertRequest(
            @JsonProperty("product_code") String productCode,
            @JsonProperty("agent_id") Long agentId,
            @JsonProperty("rate_pct") String ratePct,
            @JsonProperty("effective_from") String effectiveFrom,
            @JsonProperty("actor") String actor) {
    }

    public record EndRequest(
            @JsonProperty("product_code") String productCode,
            @JsonProperty("agent_id") Long agentId,
            @JsonProperty("effective_to") String effectiveTo,
            @JsonProperty("actor") String actor) {
    }

    @PostMapping("/upsert")
    public Map<String, Object> upsert(@RequestBody UpsertRequest req) {
        log.info("POST /rates/upsert product={} agent={} pct={} from={}",
                req.productCode(), req.agentId(), req.ratePct(), req.effectiveFrom());
        long rateId = service.upsert(req.productCode(), req.agentId(), OracleText.parseNumber(req.ratePct()),
                OracleText.parseWireDate(req.effectiveFrom()), req.actor());
        return Map.of("rate_id", rateId);
    }

    @PostMapping("/end")
    public Map<String, Object> end(@RequestBody EndRequest req) {
        log.info("POST /rates/end product={} agent={} to={}",
                req.productCode(), req.agentId(), req.effectiveTo());
        service.end(req.productCode(), req.agentId(), OracleText.parseWireDate(req.effectiveTo()), req.actor());
        return Map.of("status", "ended");
    }

    @GetMapping("/resolve")
    public Map<String, Object> resolve(
            @RequestParam(name = "product_code", required = false) String productCode,
            @RequestParam(name = "agent_id", required = false) Long agentId,
            @RequestParam(name = "as_of", required = false) String asOf) {
        log.info("GET /rates/resolve product={} agent={} as_of={}", productCode, agentId, asOf);
        long rateId = service.resolve(emptyToNull(productCode), agentId,
                OracleText.parseWireDate(emptyToNull(asOf)));
        return Map.of("rate_id", rateId);
    }

    // Oracle has no empty string: '' is NULL.
    private static String emptyToNull(String s) {
        return s == null || s.isEmpty() ? null : s;
    }
}
