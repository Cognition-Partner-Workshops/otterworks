package com.otterworks.legacyportal.common;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;

class PortalAuthenticatorTest {

    private final PortalAuthenticator authenticator = new PortalAuthenticator(TestTokens.SECRET);

    @Test
    void acceptsAccessTokenAndReadsSubjectAndRoles() {
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.addHeader("Authorization", TestTokens.bearer(TestTokens.accessToken("u1", "USER")));

        PortalPrincipal principal = authenticator.authenticate(request);

        assertThat(principal.getUserId()).isEqualTo("u1");
        assertThat(principal.getRoles()).containsExactly("USER");
        assertThat(principal.isAdmin()).isFalse();
        assertThat(principal.canActFor("u1")).isTrue();
        assertThat(principal.canActFor("u2")).isFalse();
    }

    @Test
    void adminRoleMayActForAnyUser() {
        PortalPrincipal admin =
                authenticator.authenticate(TestTokens.accessToken("admin", "ADMIN", "USER"));

        assertThat(admin.isAdmin()).isTrue();
        assertThat(admin.canActFor("u2")).isTrue();
    }

    @Test
    void rejectsMissingHeader() {
        assertThatThrownBy(() -> authenticator.authenticate(new MockHttpServletRequest()))
                .isInstanceOfSatisfying(
                        PortalAuthException.class,
                        e -> assertThat(e.getKind())
                                .isEqualTo(PortalAuthException.Kind.UNAUTHENTICATED));
    }

    @Test
    void rejectsTokenSignedWithAnotherKey() {
        String forged =
                TestTokens.accessTokenSignedWith("another-secret-that-is-long-enough-1234", "u1");

        assertThatThrownBy(() -> authenticator.authenticate(forged))
                .isInstanceOf(PortalAuthException.class);
    }

    @Test
    void rejectsRefreshToken() {
        assertThatThrownBy(() -> authenticator.authenticate(TestTokens.refreshToken("u1")))
                .isInstanceOf(PortalAuthException.class);
    }

    @Test
    void requireCanActForRaisesForbiddenForOtherUser() {
        PortalPrincipal principal = authenticator.authenticate(TestTokens.accessToken("u1"));

        assertThatThrownBy(() -> principal.requireCanActFor("u2"))
                .isInstanceOfSatisfying(
                        PortalAuthException.class,
                        e -> assertThat(e.getKind()).isEqualTo(PortalAuthException.Kind.FORBIDDEN));
    }
}
