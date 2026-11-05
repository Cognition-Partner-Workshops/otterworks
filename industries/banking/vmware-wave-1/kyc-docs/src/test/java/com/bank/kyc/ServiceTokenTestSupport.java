package com.bank.kyc;

import org.springframework.test.web.servlet.request.RequestPostProcessor;

final class ServiceTokenTestSupport {
    private ServiceTokenTestSupport() {
    }

    static RequestPostProcessor bearer(String principal, String secret) {
        return request -> {
            request.addHeader("Authorization", "Bearer " + principal + ":" + secret);
            return request;
        };
    }
}
