package com.otterworks.report.security;

import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;

/**
 * The authenticated caller of a report endpoint, as established by {@link GatewayIdentityFilter}.
 */
public final class Caller {

    private final String userId;
    private final boolean admin;

    private Caller(String userId, boolean admin) {
        this.userId = userId;
        this.admin = admin;
    }

    public static Caller from(Authentication authentication) {
        boolean admin = false;
        for (GrantedAuthority authority : authentication.getAuthorities()) {
            if ((GatewayIdentityFilter.ROLE_PREFIX + GatewayIdentityFilter.ADMIN_ROLE)
                    .equals(authority.getAuthority())) {
                admin = true;
            }
        }
        return new Caller(String.valueOf(authentication.getPrincipal()), admin);
    }

    public String getUserId() {
        return userId;
    }

    public boolean isAdmin() {
        return admin;
    }

    /** Whether this caller may see or act on a report requested by {@code requestedBy}. */
    public boolean owns(String requestedBy) {
        return admin || userId.equals(requestedBy);
    }
}
