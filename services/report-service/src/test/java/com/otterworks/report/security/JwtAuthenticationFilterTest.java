package com.otterworks.report.security;

import org.junit.After;
import org.junit.Test;
import org.springframework.mock.web.MockFilterChain;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

public class JwtAuthenticationFilterTest {

    private static final String PEER_SECRET = "peer-deployment-test-only-signing-key-0123456789abcdef01234567";
    private static final String SHORT_SECRET = "otterworks-local-dev-jwt-secret-change-me-in-production";

    @After
    public void clearContext() {
        SecurityContextHolder.clearContext();
    }

    @Test
    public void acceptsAuthServiceAccessTokenAndMapsRoles() throws Exception {
        Authentication auth = authenticate(new JwtAuthenticationFilter(TestTokens.SECRET, ""),
                TestTokens.accessToken("user-42", "ADMIN", "EDITOR"));

        assertEquals("user-42", auth.getName());
        assertTrue(ReportCaller.from(auth).isAdmin());
        assertEquals(2, auth.getAuthorities().size());
    }

    @Test
    public void acceptsHs384TokensFromShorterComposeSecret() throws Exception {
        Authentication auth = authenticate(new JwtAuthenticationFilter(SHORT_SECRET, ""),
                TestTokens.token(SHORT_SECRET, "user-1", "access", 60_000L, "VIEWER"));

        assertEquals("user-1", auth.getName());
    }

    @Test
    public void acceptsPeerDeploymentTokensWhenPeerSecretConfigured() throws Exception {
        String peerToken = TestTokens.token(PEER_SECRET, "peer-admin", "access", 60_000L, "ADMIN");

        assertNull(authenticate(new JwtAuthenticationFilter(TestTokens.SECRET, ""), peerToken));
        assertEquals("peer-admin",
                authenticate(new JwtAuthenticationFilter(TestTokens.SECRET, PEER_SECRET), peerToken).getName());
    }

    @Test
    public void rejectsRefreshTokens() throws Exception {
        assertNull(authenticate(new JwtAuthenticationFilter(TestTokens.SECRET, ""),
                TestTokens.token(TestTokens.SECRET, "user-1", "refresh", 60_000L)));
    }

    @Test
    public void failsClosedWithoutSecret() throws Exception {
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/v1/reports");
        request.addHeader("Authorization", "Bearer " + TestTokens.accessToken("user-1", "ADMIN"));
        request.addHeader("X-User-ID", "user-1");
        new JwtAuthenticationFilter("", "").doFilter(request, new MockHttpServletResponse(), new MockFilterChain());

        assertNull(SecurityContextHolder.getContext().getAuthentication());
    }

    private static Authentication authenticate(JwtAuthenticationFilter filter, String token) throws Exception {
        SecurityContextHolder.clearContext();
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/v1/reports");
        request.addHeader("Authorization", "Bearer " + token);
        filter.doFilter(request, new MockHttpServletResponse(), new MockFilterChain());
        return SecurityContextHolder.getContext().getAuthentication();
    }
}
