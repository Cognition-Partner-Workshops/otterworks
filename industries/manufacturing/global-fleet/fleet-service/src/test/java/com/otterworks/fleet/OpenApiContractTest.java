package com.otterworks.fleet;

import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
class OpenApiContractTest extends AbstractPostgresIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    void profilePathIsInOpenApiDocument() throws Exception {
        String document = mockMvc.perform(get("/v3/api-docs"))
                .andExpect(status().isOk())
                .andReturn()
                .getResponse()
                .getContentAsString();

        Files.createDirectories(Path.of("target"));
        Files.writeString(Path.of("target/openapi.json"), document);
        org.junit.jupiter.api.Assertions.assertTrue(document.contains("/api/v1/profile"));
        org.junit.jupiter.api.Assertions.assertTrue(document.contains("/api/v1/employees"));
        org.junit.jupiter.api.Assertions.assertTrue(document.contains("/api/v1/employees/{employeeNo}"));
        org.junit.jupiter.api.Assertions.assertTrue(document.contains("/api/v1/eligibility/car-request"));
        org.junit.jupiter.api.Assertions.assertTrue(document.contains("/api/v1/eligibility/mileage-claim"));
        org.junit.jupiter.api.Assertions.assertTrue(document.contains("/api/v1/eligibility/below-grade-holders"));
    }
}
