package com.otterworks.report.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.otterworks.report.dto.ReportScheduleRequest;
import com.otterworks.report.model.ReportCategory;
import com.otterworks.report.model.ReportRequest;
import com.otterworks.report.model.ReportType;
import com.otterworks.report.repository.ReportScheduleRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import java.util.Map;

import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.is;
import static org.hamcrest.Matchers.notNullValue;
import static org.hamcrest.Matchers.nullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class ReportScheduleControllerIntegrationTest {

    private static final String BASE = "/api/v1/reports/schedules";
    private static final MediaType PROBLEM_JSON = MediaType.APPLICATION_PROBLEM_JSON;

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private ReportScheduleRepository repository;

    @BeforeEach
    void clean() {
        repository.deleteAll();
    }

    @Test
    void createReturns201WithLocationAndComputedNextRun() throws Exception {
        ReportScheduleRequest request = validRequest("0 0 2 * * *", "Europe/London");

        MvcResult result = mockMvc.perform(post(BASE)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isCreated())
                .andExpect(header().string("Location", containsString(BASE + "/")))
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.id", notNullValue()))
                .andExpect(jsonPath("$.name", is("Nightly audit")))
                .andExpect(jsonPath("$.cronExpression", is("0 0 2 * * *")))
                .andExpect(jsonPath("$.timeZone", is("Europe/London")))
                .andExpect(jsonPath("$.requestedBy", is("sched-user")))
                .andExpect(jsonPath("$.enabled", is(true)))
                .andExpect(jsonPath("$.createdAt", notNullValue()))
                .andExpect(jsonPath("$.nextRunAt", notNullValue()))
                .andExpect(jsonPath("$.lastRunAt", nullValue()))
                .andExpect(jsonPath("$.template.reportName", is("Audit export")))
                .andExpect(jsonPath("$.template.category", is("AUDIT_LOG")))
                .andExpect(jsonPath("$.template.reportType", is("CSV")))
                .andExpect(jsonPath("$.template.parameters.tenant", is("acme")))
                .andReturn();

        Number id = objectMapper.readTree(result.getResponse().getContentAsString()).get("id").numberValue();

        mockMvc.perform(get(BASE + "/" + id))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id", is(id.intValue())));

        mockMvc.perform(get(BASE))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", hasSize(1)))
                .andExpect(jsonPath("$[0].name", is("Nightly audit")));
    }

    @Test
    void createWithInvalidCronReturns400ProblemDetail() throws Exception {
        ReportScheduleRequest request = validRequest("not a cron", "UTC");

        mockMvc.perform(post(BASE)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(content().contentTypeCompatibleWith(PROBLEM_JSON))
                .andExpect(jsonPath("$.status", is(400)))
                .andExpect(jsonPath("$.title", is("Invalid schedule")))
                .andExpect(jsonPath("$.detail", containsString("not a cron")));
    }

    @Test
    void createWithInvalidTimeZoneReturns400() throws Exception {
        ReportScheduleRequest request = validRequest("0 0 2 * * *", "Mars/Olympus");

        mockMvc.perform(post(BASE)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(content().contentTypeCompatibleWith(PROBLEM_JSON))
                .andExpect(jsonPath("$.detail", containsString("Mars/Olympus")));
    }

    @Test
    void createWithMissingFieldsReturns400ProblemDetail() throws Exception {
        // No name, no cron, template missing its own required fields.
        String body = """
                {"template": {"reportName": "x"}}
                """;

        mockMvc.perform(post(BASE)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isBadRequest())
                .andExpect(content().contentTypeCompatibleWith(PROBLEM_JSON))
                .andExpect(jsonPath("$.status", is(400)));
    }

    @Test
    void getUnknownReturns404ProblemDetail() throws Exception {
        mockMvc.perform(get(BASE + "/999999"))
                .andExpect(status().isNotFound())
                .andExpect(content().contentTypeCompatibleWith(PROBLEM_JSON))
                .andExpect(jsonPath("$.status", is(404)))
                .andExpect(jsonPath("$.detail", containsString("999999")));
    }

    @Test
    void deleteReturns204ThenGetReturns404() throws Exception {
        MvcResult created = mockMvc.perform(post(BASE)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(validRequest("0 */5 * * * *", "UTC"))))
                .andExpect(status().isCreated())
                .andReturn();
        Number id = objectMapper.readTree(created.getResponse().getContentAsString()).get("id").numberValue();

        mockMvc.perform(delete(BASE + "/" + id)).andExpect(status().isNoContent());
        mockMvc.perform(get(BASE + "/" + id)).andExpect(status().isNotFound());
        mockMvc.perform(delete(BASE + "/" + id)).andExpect(status().isNotFound());
    }

    private static ReportScheduleRequest validRequest(String cron, String zone) {
        ReportRequest template = new ReportRequest();
        template.setReportName("Audit export");
        template.setCategory(ReportCategory.AUDIT_LOG);
        template.setReportType(ReportType.CSV);
        template.setRequestedBy("sched-user");
        template.setParameters(Map.of("tenant", "acme"));
        return new ReportScheduleRequest("Nightly audit", cron, zone, template, null);
    }
}
