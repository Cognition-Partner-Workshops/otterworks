package com.otterworks.ottershops.payment;

import java.time.Clock;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class PaymentConfig {
    @Bean
    public PaymentProvider paymentProvider(@Value("${ottershops.payments.provider:mock}") String provider, Clock clock) {
        if (!"mock".equalsIgnoreCase(provider)) {
            throw new IllegalStateException("Unknown payment provider '" + provider + "'. Only 'mock' is available.");
        }
        return new MockPaymentProvider(clock);
    }
}
