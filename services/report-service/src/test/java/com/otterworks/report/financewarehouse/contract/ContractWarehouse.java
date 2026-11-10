package com.otterworks.report.financewarehouse.contract;

import com.fasterxml.jackson.databind.JsonNode;

interface ContractWarehouse {
    JsonNode execute(String sql, int period) throws Exception;
}
