package com.bank.statements;

import java.io.IOException;
import java.io.Reader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.security.Principal;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Properties;
import java.util.Set;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

final class StatementAccess {
    private final Map<String, Set<String>> accountsByPrincipal = new HashMap<>();

    StatementAccess(Properties mappings) {
        for (String principal : mappings.stringPropertyNames()) {
            Set<String> accounts = new LinkedHashSet<>();
            for (String value : mappings.getProperty(principal).split(",", -1)) {
                String account = value.trim();
                if (principal.trim().isEmpty() || !account.matches("[A-Z0-9]{8,20}")) {
                    throw new IllegalArgumentException("invalid statements access mapping");
                }
                accounts.add(account);
            }
            accountsByPrincipal.put(principal, Collections.unmodifiableSet(accounts));
        }
    }

    static StatementAccess load() throws IOException {
        return load(System.getenv("STATEMENTS_ACCESS_FILE"));
    }

    static StatementAccess load(String path) throws IOException {
        Properties mappings = new Properties();
        if (path != null && !path.trim().isEmpty()) {
            try (Reader reader = Files.newBufferedReader(Paths.get(path), StandardCharsets.UTF_8)) {
                mappings.load(reader);
            }
        }
        return new StatementAccess(mappings);
    }

    Set<String> accounts(HttpServletRequest request, HttpServletResponse response) throws IOException {
        response.setHeader("Cache-Control", "no-store");
        Principal principal = request.getUserPrincipal();
        if (principal == null) {
            response.sendError(HttpServletResponse.SC_UNAUTHORIZED);
            return null;
        }
        Set<String> accounts = accountsByPrincipal.get(principal.getName());
        if (accounts == null || accounts.isEmpty()) {
            response.sendError(HttpServletResponse.SC_FORBIDDEN);
            return null;
        }
        return accounts;
    }
}
