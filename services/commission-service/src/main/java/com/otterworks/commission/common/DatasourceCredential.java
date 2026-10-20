package com.otterworks.commission.common;

import org.springframework.core.env.Environment;
import org.springframework.stereotype.Component;

/**
 * The datasource password has no default in configuration; it comes from the
 * secret store as COMMISSION_DB_PASSWORD. Spring Boot's binder would pass an
 * unresolved placeholder through as the literal password, so an unset or blank
 * value stops the service at startup instead.
 */
@Component
public class DatasourceCredential {

    static final String PASSWORD = "spring.datasource.password";

    public DatasourceCredential(Environment env) {
        String password;
        try {
            password = env.getProperty(PASSWORD);
        } catch (IllegalArgumentException unresolved) {
            password = null;
        }
        if (password == null || password.isBlank()) {
            throw new IllegalStateException(
                    "COMMISSION_DB_PASSWORD must be set from the secret store; the datasource has no default password");
        }
    }
}
