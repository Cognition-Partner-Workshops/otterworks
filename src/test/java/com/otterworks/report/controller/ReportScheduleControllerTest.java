package com.otterworks.report.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.otterworks.report.model.ReportCategory;
import com.otterworks.report.model.ReportRequest;
import com.otterworks.report.model.ReportScheduleRequest;
import com.otterworks.report.model.ReportType;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class ReportScheduleControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    private ReportScheduleRequest validRequest() {
        ReportRequest template = new ReportRequest();
        template.setReportName("Daily Usage Report");
        template.setCategory(ReportCategory.USAGE_ANALYTICS);
        template.setReportType(ReportType.PDF);
        template.setRequestedBy("scheduler-user");
        return new ReportScheduleRequest(
                "Daily Usage",
                "0 0 8 * * MON-FRI",
                "America/New_York",
                template,
                "admin-user"
        );
    }

    @Test
    void createScheduleReturns201() throws Exception {
        mockMvc.perform(post("/api/v1/reports/schedules")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(validRequest())))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.name").value("Daily Usage"))
                .andExpect(jsonPath("$.cronExpression").value("0 0 8 * * MON-FRI"))
                .andExpect(jsonPath("$.enabled").value(true));
    }

    @Test
    void createScheduleWithInvalidCronReturns400() throws Exception {
        ReportScheduleRequest bad = new ReportScheduleRequest(
                "Bad Schedule",
                "not-a-cron",
                "America/New_York",
                validRequest().template(),
                "admin-user"
        );
        mockMvc.perform(post("/api/v1/reports/schedules")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(bad)))
                .andExpect(status().isBadRequest());
    }

    @Test
    void createScheduleWithMissingFieldsReturns400() throws Exception {
        ReportScheduleRequest bad = new ReportScheduleRequest(
                null, null, null, null, null
        );
        mockMvc.perform(post("/api/v1/reports/schedules")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(bad)))
                .andExpect(status().isBadRequest());
    }

    @Test
    void getScheduleReturns404WhenNotFound() throws Exception {
        mockMvc.perform(get("/api/v1/reports/schedules/9999"))
                .andExpect(status().isNotFound());
    }

    @Test
    void deleteScheduleReturns404WhenNotFound() throws Exception {
        mockMvc.perform(delete("/api/v1/reports/schedules/9999"))
                .andExpect(status().isNotFound());
    }

    @Test
    void fullCrudLifecycle() throws Exception {
        // Create
        MvcResult result = mockMvc.perform(post("/api/v1/reports/schedules")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(validRequest())))
                .andExpect(status().isCreated())
                .andReturn();

        String id = objectMapper.readTree(result.getResponse().getContentAsString()).get("id").asText();

        // Get by ID
        mockMvc.perform(get("/api/v1/reports/schedules/" + id))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.name").value("Daily Usage"));

        // List
        mockMvc.perform(get("/api/v1/reports/schedules"))
                .andExpect(status().isOk());

        // Delete
        mockMvc.perform(delete("/api/v1/reports/schedules/" + id))
                .andExpect(status().isNoContent());

        // Verify deleted
        mockMvc.perform(get("/api/v1/reports/schedules/" + id))
                .andExpect(status().isNotFound());
    }
}
