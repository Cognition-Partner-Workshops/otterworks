package com.bank.statements;

import static org.junit.Assert.assertEquals;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;
import org.junit.Test;

public class AppConfigTest {
    @Test
    public void environmentOverridesMountedFile() throws Exception {
        Path config = Files.createTempFile("statements", ".properties");
        try {
            Files.write(config, "bank.name=Fixture\nstatement.page.size=12\n".getBytes(StandardCharsets.UTF_8));
            Map<String, String> env = new HashMap<>();
            env.put("CONFIG_FILE", config.toString());
            assertEquals("Fixture", AppConfig.load(env).getProperty("bank.name"));
            env.put("BANK_NAME", "Override");
            env.put("STATEMENT_PAGE_SIZE", "7");
            assertEquals("Override", AppConfig.load(env).getProperty("bank.name"));
            assertEquals("7", AppConfig.load(env).getProperty("statement.page.size"));
        } finally {
            Files.delete(config);
        }
    }

    @Test(expected = IllegalStateException.class)
    public void explicitMissingFileFails() {
        Map<String, String> env = new HashMap<>();
        env.put("CONFIG_FILE", "/not-present/statements.properties");
        AppConfig.load(env);
    }

    @Test(expected = IllegalStateException.class)
    public void nonPositivePageSizeFails() {
        Map<String, String> env = new HashMap<>();
        env.put("STATEMENT_PAGE_SIZE", "0");
        AppConfig.load(env);
    }
}
