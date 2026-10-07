package com.otterworks.preferences;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

/** Full-context test of the routes legacy-portal served for this context (see parity/ for the HTTP replay). */
@SpringBootTest
@AutoConfigureMockMvc
class PreferencesServiceApplicationTest {

    @Autowired private MockMvc mockMvc;

    @Test
    void healthEndpointReportsUp() throws Exception {
        mockMvc.perform(get("/health"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("UP"))
                .andExpect(jsonPath("$.service").value("preferences-service"));
    }

    @Test
    void actuatorHealthIsUp() throws Exception {
        mockMvc.perform(get("/actuator/health")).andExpect(status().isOk());
    }

    @Test
    void unknownUserGetsDefaults() throws Exception {
        mockMvc.perform(get("/api/preferences/newuser"))
                .andExpect(status().isOk())
                .andExpect(
                        content()
                                .json(
                                        "{\"userId\":\"newuser\",\"theme\":\"light\",\"locale\":\"en-US\",\"emailNotifications\":true}",
                                        true));
    }

    @Test
    void putStoresAndOmittedEmailNotificationsIsFalse() throws Exception {
        mockMvc.perform(
                        put("/api/preferences/mvc1")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content("{\"theme\":\"dark\",\"locale\":\"fr-FR\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.emailNotifications").value(false));

        mockMvc.perform(get("/api/preferences/mvc1"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.theme").value("dark"))
                .andExpect(jsonPath("$.locale").value("fr-FR"));
    }

    @Test
    void blankOrOversizedFieldsAreRejected() throws Exception {
        mockMvc.perform(
                        put("/api/preferences/mvc2")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content("{\"theme\":\"dark\",\"locale\":\"  \"}"))
                .andExpect(status().isBadRequest());
        mockMvc.perform(
                        put("/api/preferences/mvc2")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content("{\"theme\":\"ttttttttttttttttttttt\",\"locale\":\"en-GB\"}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void onlyGetAndPutAreRouted() throws Exception {
        mockMvc.perform(
                        post("/api/preferences/mvc3")
                                .contentType(MediaType.APPLICATION_JSON)
                                .content("{\"theme\":\"dark\",\"locale\":\"en-US\"}"))
                .andExpect(status().isMethodNotAllowed());
        mockMvc.perform(
                        put("/api/preferences/mvc3")
                                .contentType(MediaType.TEXT_PLAIN)
                                .content("theme=dark"))
                .andExpect(status().isUnsupportedMediaType());
    }
}
