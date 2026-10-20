package com.bank.statements;

import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.Properties;

public final class AppConfig {
    private static final String CONF_FILE = "/opt/app/conf/statements.properties";
    private static Properties props;

    private AppConfig() {
    }

    public static synchronized Properties get() {
        if (props == null) {
            Properties p = new Properties();
            try (InputStream in = new FileInputStream(CONF_FILE)) {
                p.load(in);
            } catch (IOException e) {
                throw new IllegalStateException("cannot read " + CONF_FILE, e);
            }
            props = p;
        }
        return props;
    }

    public static String bankName() {
        return get().getProperty("bank.name", "Statements");
    }

    public static int pageSize() {
        return Integer.parseInt(get().getProperty("statement.page.size", "50"));
    }
}
