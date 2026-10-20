package com.bank.statements;

import java.util.Map;

/** Settings from the environment; the password arrives from a Kubernetes Secret reference. */
public final class AppConfig {
    static final String BANK_NAME = "STATEMENTS_BANK_NAME";
    static final String PAGE_SIZE = "STATEMENTS_PAGE_SIZE";
    static final String DB_URL = "STATEMENTS_DB_URL";
    static final String DB_USER = "STATEMENTS_DB_USER";
    static final String DB_PASSWORD = "STATEMENTS_DB_PASSWORD";

    private final String bankName;
    private final int pageSize;
    private final String dbUrl;
    private final String dbUser;
    private final String dbPassword;

    private AppConfig(Map<String, String> env) {
        bankName = env.getOrDefault(BANK_NAME, "Statements");
        pageSize = Integer.parseInt(env.getOrDefault(PAGE_SIZE, "50"));
        dbUrl = required(env, DB_URL);
        dbUser = required(env, DB_USER);
        dbPassword = required(env, DB_PASSWORD);
    }

    public static AppConfig fromEnv() {
        return from(System.getenv());
    }

    static AppConfig from(Map<String, String> env) {
        return new AppConfig(env);
    }

    private static String required(Map<String, String> env, String name) {
        String v = env.get(name);
        if (v == null || v.isEmpty()) {
            throw new IllegalStateException("environment variable " + name + " is not set");
        }
        return v;
    }

    public String bankName() {
        return bankName;
    }

    public int pageSize() {
        return pageSize;
    }

    String dbUrl() {
        return dbUrl;
    }

    String dbUser() {
        return dbUser;
    }

    String dbPassword() {
        return dbPassword;
    }
}
