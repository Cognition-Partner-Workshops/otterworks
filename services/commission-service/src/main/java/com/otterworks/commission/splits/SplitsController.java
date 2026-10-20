package com.otterworks.commission.splits;

import java.util.LinkedHashMap;
import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class SplitsController {

    private static final Logger log = LoggerFactory.getLogger(SplitsController.class);

    private final SplitsService service;

    public SplitsController(SplitsService service) {
        this.service = service;
    }

    /** {@code policyId} is "null" when the caller passed a NULL p_policy_id. */
    @PostMapping("/policies/{policyId}/splits")
    public Map<String, Object> setSplits(@PathVariable String policyId, @RequestBody SetSplitsRequest req) {
        Long id = "null".equals(policyId) ? null : Long.valueOf(policyId);
        log.info("POST /policies/{policyId}/splits agents={} actor={}",
                req.splits() == null ? "null" : req.splits().size(), req.actor());
        int n = service.setSplits(id, req.splits(), req.actor());
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("policy_id", id);
        body.put("agents", n);
        return body;
    }
}
