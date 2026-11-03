package com.otterworks.ottershops.auth;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;

import java.util.UUID;

/** Creates the demo shopper account on first boot so the signed-in flow works on a fresh database. */
@Component
public class DemoShopperSeeder implements ApplicationRunner {
    private static final Logger log = LoggerFactory.getLogger(DemoShopperSeeder.class);
    private final CustomerRepository customers;
    private final AuthService auth;
    private final String email;
    private final String password;

    public DemoShopperSeeder(CustomerRepository customers, AuthService auth,
                             @Value("${ottershops.demo-shopper.email:maya@ottershops.test}") String email,
                             @Value("${ottershops.demo-shopper.password:otters-2026}") String password) {
        this.customers = customers;
        this.auth = auth;
        this.email = email;
        this.password = password;
    }

    @Override
    public void run(ApplicationArguments args) {
        if (email.isBlank() || customers.findByEmail(email).isPresent()) return;
        customers.insert(UUID.randomUUID(), email, auth.hash(password), "Maya", "Rivers");
        log.info("created demo shopper {}", email);
    }
}
