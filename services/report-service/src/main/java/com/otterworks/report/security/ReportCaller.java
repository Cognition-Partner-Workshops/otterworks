package com.otterworks.report.security;

import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;

/** The authenticated caller of a report endpoint. */
public final class ReportCaller {

    public static final String ADMIN_AUTHORITY = "ROLE_ADMIN";

    private final String userId;
    private final boolean admin;

    private ReportCaller(String userId, boolean admin) {
        this.userId = userId;
        this.admin = admin;
    }

    public static ReportCaller from(Authentication authentication) {
        boolean admin = false;
        for (GrantedAuthority authority : authentication.getAuthorities()) {
            if (ADMIN_AUTHORITY.equals(authority.getAuthority())) {
                admin = true;
                break;
            }
        }
        return new ReportCaller(authentication.getName(), admin);
    }

    public String getUserId() {
        return userId;
    }

    public boolean isAdmin() {
        return admin;
    }

    /** Admins may act on any report; everyone else only on reports they requested. */
    public boolean canAccess(String requestedBy) {
        return admin || userId.equals(requestedBy);
    }
}
