package com.bank.statements;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertThrows;
import static org.junit.Assert.assertTrue;

import java.util.HashMap;
import java.util.Map;
import org.junit.Test;

public class AppConfigTest {
    private static Map<String, String> db() {
        Map<String, String> env = new HashMap<>();
        env.put("STATEMENTS_DB_URL", "jdbc:postgresql://db:5432/bankwave");
        env.put("STATEMENTS_DB_USER", "statements_app");
        env.put("STATEMENTS_DB_PASSWORD", "unit-test-only");
        return env;
    }

    @Test
    public void defaultsMatchTheOldPropertiesFallbacks() {
        AppConfig c = AppConfig.from(db());
        assertEquals("Statements", c.bankName());
        assertEquals(50, c.pageSize());
    }

    @Test
    public void readsSettingsFromTheEnvironment() {
        Map<String, String> env = db();
        env.put("STATEMENTS_BANK_NAME", "Halvergate Bank");
        env.put("STATEMENTS_PAGE_SIZE", "20");
        AppConfig c = AppConfig.from(env);
        assertEquals("Halvergate Bank", c.bankName());
        assertEquals(20, c.pageSize());
        assertEquals("jdbc:postgresql://db:5432/bankwave", c.dbUrl());
        assertEquals("statements_app", c.dbUser());
    }

    @Test
    public void missingPasswordNamesTheVariable() {
        Map<String, String> env = db();
        env.remove("STATEMENTS_DB_PASSWORD");
        IllegalStateException e = assertThrows(IllegalStateException.class, () -> AppConfig.from(env));
        assertTrue(e.getMessage().contains("STATEMENTS_DB_PASSWORD"));
    }
}
