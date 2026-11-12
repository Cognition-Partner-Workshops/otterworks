package com.otterworks.report.security;

import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;

/**
 * The caller the gateway authenticated: who they are and whether they may act on
 * every user's reports.
 */
public final class CallerIdentity {

    public static final String ADMIN_AUTHORITY = "ROLE_ADMIN";

    private final String userId;
    private final boolean admin;

    public CallerIdentity(String userId, boolean admin) {
        this.userId = userId;
        this.admin = admin;
    }

    public static CallerIdentity from(Authentication authentication) {
        boolean admin = false;
        for (GrantedAuthority authority : authentication.getAuthorities()) {
            if (ADMIN_AUTHORITY.equals(authority.getAuthority())) {
                admin = true;
                break;
            }
        }
        return new CallerIdentity(authentication.getName(), admin);
    }

    public String getUserId() {
        return userId;
    }

    public boolean isAdmin() {
        return admin;
    }

    /** Whether this caller may read, download or delete a report owned by {@code ownerId}. */
    public boolean canAccess(String ownerId) {
        return admin || (ownerId != null && ownerId.equals(userId));
    }
}
