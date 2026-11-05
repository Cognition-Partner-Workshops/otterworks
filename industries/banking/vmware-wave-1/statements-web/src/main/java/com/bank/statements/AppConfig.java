package com.bank.statements;

import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.Properties;
import java.util.Map;
import java.nio.file.Files;
import java.nio.file.Paths;

public final class AppConfig {
    private static final String CONF_FILE = "/opt/app/conf/statements.properties";
    private static Properties props;

    private AppConfig() {
    }

    public static synchronized Properties get() {
        if (props == null) {
            props = load(System.getenv());
        }
        return props;
    }

    static Properties load(Map<String, String> env) {
        Properties p = new Properties();
        String path = env.get("CONFIG_FILE");
        if (path == null && Files.isRegularFile(Paths.get(CONF_FILE))) {
            path = CONF_FILE;
        }
        try (InputStream defaults = AppConfig.class.getResourceAsStream("/statements.properties")) {
            if (defaults != null) {
                p.load(defaults);
            }
            if (path != null) {
                try (InputStream in = new FileInputStream(path)) {
                    p.load(in);
                }
            }
        } catch (IOException e) {
            throw new IllegalStateException("cannot read application configuration", e);
        }
        if (env.containsKey("BANK_NAME")) {
            p.setProperty("bank.name", env.get("BANK_NAME"));
        }
        if (env.containsKey("STATEMENT_PAGE_SIZE")) {
            p.setProperty("statement.page.size", env.get("STATEMENT_PAGE_SIZE"));
        }
        if (Integer.parseInt(p.getProperty("statement.page.size", "50")) < 1) {
            throw new IllegalStateException("statement.page.size must be positive");
        }
        return p;
    }

    public static String bankName() {
        return get().getProperty("bank.name", "Statements");
    }

    public static int pageSize() {
        return Integer.parseInt(get().getProperty("statement.page.size", "50"));
    }
}
