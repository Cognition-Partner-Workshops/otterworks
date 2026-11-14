package com.otterworks.preferences;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/** User-preferences bounded context, extracted from services/legacy-portal. */
@SpringBootApplication
public class PreferencesServiceApplication {

    public static void main(String[] args) {
        SpringApplication.run(PreferencesServiceApplication.class, args);
    }
}
