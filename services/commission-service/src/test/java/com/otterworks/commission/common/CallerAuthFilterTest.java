package com.otterworks.commission.common;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockFilterChain;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

class CallerAuthFilterTest {

    private static MockFilterChain run(CallerAuthFilter filter, String method, String path, String authorization,
            MockHttpServletResponse res) throws Exception {
        MockHttpServletRequest req = new MockHttpServletRequest(method, path);
        if (authorization != null) {
            req.addHeader("Authorization", authorization);
        }
        MockFilterChain chain = new MockFilterChain();
        filter.doFilter(req, res, chain);
        return chain;
    }

    @Test
    @DisplayName("the configured bearer token reaches the rule endpoint")
    void acceptsConfiguredToken() throws Exception {
        MockHttpServletResponse res = new MockHttpServletResponse();
        MockFilterChain chain = run(new CallerAuthFilter("s3cret"), "POST", "/policies/4/splits", "Bearer s3cret", res);
        assertThat(chain.getRequest()).isNotNull();
        assertThat(res.getStatus()).isEqualTo(200);
    }

    @Test
    @DisplayName("missing, wrong or non-bearer credentials get 401 and never reach the rule")
    void refusesOtherCallers() throws Exception {
        CallerAuthFilter filter = new CallerAuthFilter("s3cret");
        for (String auth : new String[] {null, "", "Bearer ", "Bearer s3cre", "Bearer s3cretX", "Basic s3cret", "s3cret"}) {
            MockHttpServletResponse res = new MockHttpServletResponse();
            MockFilterChain chain = run(filter, "POST", "/policies/4/commission", auth, res);
            assertThat(chain.getRequest()).as("auth=%s", auth).isNull();
            assertThat(res.getStatus()).as("auth=%s", auth).isEqualTo(401);
            assertThat(res.getHeader("WWW-Authenticate")).isEqualTo("Bearer");
        }
    }

    @Test
    @DisplayName("with no token configured every rule call is refused")
    void failsClosedWithoutToken() throws Exception {
        for (String configured : new String[] {null, "", "  "}) {
            MockHttpServletResponse res = new MockHttpServletResponse();
            MockFilterChain chain = run(new CallerAuthFilter(configured), "POST", "/policies/4/splits", "Bearer ", res);
            assertThat(chain.getRequest()).isNull();
            assertThat(res.getStatus()).isEqualTo(401);
        }
    }

    @Test
    @DisplayName("GET /actuator/health stays open for the probes; nothing else does")
    void healthProbeIsOpen() throws Exception {
        CallerAuthFilter filter = new CallerAuthFilter("s3cret");
        assertThat(run(filter, "GET", "/actuator/health", null, new MockHttpServletResponse()).getRequest()).isNotNull();
        assertThat(run(filter, "GET", "/actuator/health/liveness", null, new MockHttpServletResponse()).getRequest())
                .isNotNull();
        assertThat(run(filter, "POST", "/actuator/health", null, new MockHttpServletResponse()).getRequest()).isNull();
        assertThat(run(filter, "GET", "/actuator/healthz", null, new MockHttpServletResponse()).getRequest()).isNull();
        assertThat(run(filter, "GET", "/rates/resolve", null, new MockHttpServletResponse()).getRequest()).isNull();
    }
}
