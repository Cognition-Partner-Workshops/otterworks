package com.otterworks.report.preview;

import com.otterworks.report.service.ReportHeaderRenderer;
import org.junit.Before;
import org.junit.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

public class PreviewControllerTest {

    private static final String URL = "/api/v1/reports/templates/monthly-summary/preview";

    private MockMvc mvc;

    @Before
    public void setUp() {
        PreviewTemplates templates = new PreviewTemplates();
        mvc = MockMvcBuilders.standaloneSetup(new PreviewController(new PreviewAuthorizer(templates),
                new PreviewService(templates, new ReportHeaderRenderer())))
                .setControllerAdvice(new PreviewExceptionHandler()).build();
    }

    @Test
    public void ownerGetsRenderedPreview() throws Exception {
        mvc.perform(get(URL).principal(() -> "ops-analyst"))
                .andExpect(status().isOk())
                .andExpect(content().string("Monthly summary | INTERNAL USE ONLY"));
    }

    @Test
    public void nonOwnerGetsForbiddenJson() throws Exception {
        mvc.perform(get(URL).principal(() -> "other"))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.error").value("template preview denied"));
    }

    @Test
    public void adminGetsPreview() throws Exception {
        mvc.perform(get(URL).principal(() -> "other").with(request -> {
            request.addUserRole("REPORT_ADMIN");
            return request;
        })).andExpect(status().isOk());
    }

    @Test
    public void anonymousGetsForbidden() throws Exception {
        mvc.perform(get(URL)).andExpect(status().isForbidden());
    }

    @Test
    public void unknownTemplateGetsForbidden() throws Exception {
        mvc.perform(get("/api/v1/reports/templates/unknown/preview").principal(() -> "ops-analyst"))
                .andExpect(status().isForbidden());
    }
}
