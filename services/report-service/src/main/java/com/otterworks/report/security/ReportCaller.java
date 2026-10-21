package com.otterworks.report.security;

import com.otterworks.report.model.Report;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;

/**
 * The authenticated identity a report request is evaluated against.
 *
 * Built from the JWT the {@link JwtAuthFilter} validated: the token subject is the user id
 * and {@code ROLE_ADMIN} marks an operator who may read or delete any user's reports.
 */
public final class ReportCaller {

    public static final String ROLE_ADMIN = "ROLE_ADMIN";

    private final String userId;
    private final boolean admin;

    public ReportCaller(String userId, boolean admin) {
        if (userId == null || userId.trim().isEmpty()) {
            throw new IllegalArgumentException("caller user id is required");
        }
        this.userId = userId;
        this.admin = admin;
    }

    public static ReportCaller from(Authentication authentication) {
        if (authentication == null || !authentication.isAuthenticated()
                || authentication.getPrincipal() == null) {
            throw new IllegalStateException("no authenticated caller");
        }
        boolean isAdmin = false;
        for (GrantedAuthority authority : authentication.getAuthorities()) {
            if (ROLE_ADMIN.equals(authority.getAuthority())) {
                isAdmin = true;
                break;
            }
        }
        return new ReportCaller(authentication.getPrincipal().toString(), isAdmin);
    }

    public String getUserId() {
        return userId;
    }

    public boolean isAdmin() {
        return admin;
    }

    /** True when this caller owns the report or is an admin. */
    public boolean canAccess(Report report) {
        return admin || (report != null && userId.equals(report.getRequestedBy()));
    }

    @Override
    public String toString() {
        return "ReportCaller{userId='" + userId + "', admin=" + admin + '}';
    }
}
