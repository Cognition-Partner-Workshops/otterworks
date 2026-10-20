package com.otterworks.commission.common;

import java.util.Arrays;
import java.util.List;

import org.springframework.core.env.Environment;
import org.springframework.stereotype.Component;

/**
 * The database this instance runs against, chosen by COMMISSION_BACKEND
 * (the Spring profile {@code oracle} or {@code postgres}). Exactly one must be
 * active; anything else stops the service at startup.
 */
@Component
public class Backend {

    public enum Kind {
        ORACLE, POSTGRES
    }

    private final Kind kind;

    public Backend(Environment env) {
        this.kind = fromProfiles(env.getActiveProfiles());
    }

    public Kind kind() {
        return kind;
    }

    public boolean isPostgres() {
        return kind == Kind.POSTGRES;
    }

    static Kind fromProfiles(String[] profiles) {
        List<Kind> picked = Arrays.stream(profiles)
                .filter(p -> p.equals("oracle") || p.equals("postgres"))
                .map(p -> p.equals("oracle") ? Kind.ORACLE : Kind.POSTGRES)
                .distinct()
                .toList();
        if (picked.size() != 1) {
            throw new IllegalStateException("COMMISSION_BACKEND must be exactly one of oracle, postgres; active profiles: "
                    + Arrays.toString(profiles));
        }
        return picked.get(0);
    }
}
