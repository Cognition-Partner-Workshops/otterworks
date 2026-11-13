package com.otterworks.report.preview;

import org.junit.Before;
import org.junit.Test;
import org.springframework.mock.web.MockHttpServletRequest;

import java.io.InputStream;
import java.security.Principal;
import java.util.Properties;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertThrows;

public class PreviewAuthorizerTest {

    private PreviewAuthorizer authorizer;
    private MockHttpServletRequest request;

    @Before
    public void setUp() {
        authorizer = new PreviewAuthorizer(new PreviewTemplates());
        request = new MockHttpServletRequest();
    }

    @Test
    public void deniesNonOwner() {
        assertThrows(PreviewDeniedException.class,
                () -> authorizer.authorize("monthly-summary", () -> "other", request));
    }

    @Test
    public void deniesAnonymousEvenWithAdminRole() {
        request.addUserRole("REPORT_ADMIN");
        assertThrows(PreviewDeniedException.class,
                () -> authorizer.authorize("monthly-summary", null, request));
    }

    @Test
    public void allowsOwner() {
        authorizer.authorize("monthly-summary", () -> "ops-analyst", request);
    }

    @Test
    public void allowsReportAdmin() {
        request.addUserRole("REPORT_ADMIN");
        authorizer.authorize("monthly-summary", () -> "other", request);
    }

    @Test
    public void deniesUnknownTemplateEvenForAdmin() {
        request.addUserRole("REPORT_ADMIN");
        assertThrows(PreviewDeniedException.class,
                () -> authorizer.authorize("unknown", () -> "ops-analyst", request));
    }

    @Test
    public void deniesBlankAndUnresolvedOwnersEvenForAdmin() {
        Properties properties = new Properties();
        properties.setProperty("preview.owner.blank", "   ");
        properties.setProperty("preview.owner.unresolved", "${missing:owner}");
        PreviewAuthorizer configured = new PreviewAuthorizer(new PreviewTemplates(properties));
        request.addUserRole("REPORT_ADMIN");
        for (String id : new String[] {"blank", "unresolved"}) {
            assertThrows(PreviewDeniedException.class,
                    () -> configured.authorize(id, () -> "ops-analyst", request));
        }
    }

    @Test
    public void resolvesLegacyOwnerAndAllowsOnlyThatOwner() throws Exception {
        Properties properties = new Properties();
        try (InputStream in = getClass().getClassLoader()
                .getResourceAsStream("report-template-preview-legacy.properties")) {
            properties.load(in);
        }
        PreviewAuthorizer legacy = new PreviewAuthorizer(new PreviewTemplates(properties));
        Principal owner = () -> "ops-analyst";
        assertEquals(owner.getName(), legacy.resolveOwner("legacy-rollup"));
        legacy.authorize("legacy-rollup", owner, request);
        assertThrows(PreviewDeniedException.class,
                () -> legacy.authorize("legacy-rollup", () -> "other", request));
    }

    @Test
    public void rejectsExecutableOwnerDirectivesEvenForAdmin() {
        request.addUserRole("REPORT_ADMIN");
        for (String directive : new String[] {
                "${script:javascript:3+4}",
                "${script:javascript:\"ops-\"+\"analyst\"}",
                "prefix-${script:javascript:\"ops-analyst\"}"}) {
            Properties properties = new Properties();
            properties.setProperty("preview.owner.dynamic", directive);
            PreviewAuthorizer configured = new PreviewAuthorizer(new PreviewTemplates(properties));
            assertThrows(PreviewDeniedException.class,
                    () -> configured.authorize("dynamic", () -> "ops-analyst", request));
        }
    }
}
