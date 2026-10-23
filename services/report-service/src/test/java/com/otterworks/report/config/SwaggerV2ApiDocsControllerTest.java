package com.otterworks.report.config;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import static org.hamcrest.Matchers.containsInAnyOrder;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.startsWith;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
public class SwaggerV2ApiDocsControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    public void v2ApiDocsIsSwagger2WithTheSamePaths() throws Exception {
        mockMvc.perform(get("/v2/api-docs"))
                .andExpect(status().isOk())
                .andExpect(content().contentType("application/json"))
                .andExpect(jsonPath("$.swagger").value("2.0"))
                .andExpect(jsonPath("$.openapi").doesNotExist())
                .andExpect(jsonPath("$.paths['/api/v1/reports'].*", hasSize(2)))
                .andExpect(jsonPath("$.paths['/api/v1/reports/{id}/download'].get.responses['200'].schema.type")
                        .value("file"))
                .andExpect(jsonPath("$.paths['/api/v1/reports'].post.parameters[0].in").value("body"))
                .andExpect(jsonPath("$.paths['/api/v1/reports'].post.parameters[0].schema['$ref']",
                        startsWith("#/definitions/")))
                .andExpect(jsonPath("$.definitions.ReportRequest.required",
                        containsInAnyOrder("reportName", "category", "reportType", "requestedBy")));
    }

    @Test
    public void v3ApiDocsIsServed() throws Exception {
        mockMvc.perform(get("/v3/api-docs"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.openapi", startsWith("3.")));
    }
}
