package com.otterworks.report.financewarehouse;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.dao.DataAccessException;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
@ConditionalOnProperty(name = "finance.warehouse.enabled", havingValue = "true", matchIfMissing = true)
public class FinanceReconciliationController {
    private final FinanceWarehouse warehouse;

    public FinanceReconciliationController(FinanceWarehouse warehouse) {
        this.warehouse = warehouse;
    }

    @GetMapping("/api/v1/reports/finance-reconciliation")
    public FinanceReconciliation report(@RequestParam("period") String period) {
        if (!period.matches("[1-9][0-9]{3}(0[1-9]|1[0-2])")) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "period must be YYYYMM");
        }
        try {
            return warehouse.reconcile(Integer.parseInt(period));
        } catch (DataAccessException ex) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "finance warehouse unavailable");
        }
    }
}
