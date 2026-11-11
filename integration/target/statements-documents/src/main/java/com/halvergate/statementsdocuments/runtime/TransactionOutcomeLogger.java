package com.halvergate.statementsdocuments.runtime;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

@Component
public class TransactionOutcomeLogger {
    private static final Logger LOG = LoggerFactory.getLogger(TransactionOutcomeLogger.class);

    public void register(String requestId) {
        if (!TransactionSynchronizationManager.isSynchronizationActive()) {
            throw new IllegalStateException("No transaction for " + requestId);
        }
        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCompletion(int status) {
                LOG.info("requestId={} {}", requestId,
                    status == STATUS_COMMITTED ? "COMMIT" : "ROLLBACK");
            }
        });
    }
}
