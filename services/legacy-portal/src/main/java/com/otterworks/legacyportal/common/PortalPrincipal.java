package com.otterworks.legacyportal.common;

import java.util.Collections;
import java.util.List;
import java.util.Objects;

/** The identity of the caller, as established by {@link PortalAuthenticator} from the request. */
public final class PortalPrincipal {

    public static final String ADMIN_ROLE = "ADMIN";

    private final String userId;
    private final List<String> roles;

    public PortalPrincipal(String userId, List<String> roles) {
        this.userId = Objects.requireNonNull(userId, "userId");
        this.roles = roles == null ? Collections.emptyList() : List.copyOf(roles);
    }

    public String getUserId() {
        return userId;
    }

    public List<String> getRoles() {
        return roles;
    }

    public boolean isAdmin() {
        return roles.contains(ADMIN_ROLE);
    }

    /** True when the caller is {@code userId} or holds the admin role. */
    public boolean canActFor(String userId) {
        return this.userId.equals(userId) || isAdmin();
    }

    /**
     * Ensures the caller may act on behalf of {@code userId}; otherwise fails with 403. Both
     * controllers that key data by user id go through this check.
     */
    public void requireCanActFor(String userId) {
        if (!canActFor(userId)) {
            throw new PortalAuthException(
                    PortalAuthException.Kind.FORBIDDEN,
                    "Not allowed to act on behalf of user " + userId);
        }
    }
}
