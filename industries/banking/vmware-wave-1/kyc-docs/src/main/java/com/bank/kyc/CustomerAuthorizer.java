package com.bank.kyc;

import java.util.Arrays;
import java.util.Set;
import java.util.stream.Collectors;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.Authentication;
import org.springframework.stereotype.Component;

@Component
public class CustomerAuthorizer {
    private final String uploader;
    private final String reviewer;
    private final Set<String> uploaderCustomers;
    private final Set<String> reviewerCustomers;

    public CustomerAuthorizer(@Value("${kyc.auth.uploader.username}") String uploader,
                              @Value("${kyc.auth.reviewer.username}") String reviewer,
                              @Value("${kyc.auth.uploader.customers}") String uploaderCustomers,
                              @Value("${kyc.auth.reviewer.customers}") String reviewerCustomers) {
        this.uploader = uploader;
        this.reviewer = reviewer;
        this.uploaderCustomers = customers(uploaderCustomers);
        this.reviewerCustomers = customers(reviewerCustomers);
    }

    private static Set<String> customers(String value) {
        return Arrays.stream(value.split(","))
                .map(String::trim)
                .filter(customer -> DocumentStore.CUSTOMER.matcher(customer).matches())
                .collect(Collectors.toSet());
    }

    public void requireCustomer(Authentication authentication, String customer) {
        if (authentication != null && authentication.isAuthenticated()) {
            String name = authentication.getName();
            if ((!uploader.isBlank() && name.equals(uploader) && uploaderCustomers.contains(customer))
                    || (!reviewer.isBlank() && name.equals(reviewer) && reviewerCustomers.contains(customer))) {
                return;
            }
        }
        throw new AccessDeniedException("forbidden");
    }
}
