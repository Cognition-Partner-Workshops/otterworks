package com.otterworks.auth.controller;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.otterworks.auth.repository.RefreshTokenRepository;
import com.otterworks.auth.repository.UserRepository;
import com.otterworks.auth.repository.UserSettingsRepository;
import java.util.UUID;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class SettingsControllerIntegrationTest {

  @Autowired private MockMvc mockMvc;
  @Autowired private ObjectMapper objectMapper;
  @Autowired private UserRepository userRepository;
  @Autowired private UserSettingsRepository settingsRepository;
  @Autowired private RefreshTokenRepository refreshTokenRepository;

  @BeforeEach
  @AfterEach
  void cleanUp() {
    settingsRepository.deleteAll();
    refreshTokenRepository.deleteAll();
    userRepository.deleteAll();
  }

  @Test
  void getSettings_shouldReturnDefaultsAndCreateRowForNewUser() throws Exception {
    RegisteredUser user = register("settings-defaults@otterworks.dev");
    assertThat(settingsRepository.findById(user.id())).isEmpty();

    mockMvc
        .perform(get("/api/v1/settings").header("Authorization", user.bearer()))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.notificationEmail").value(true))
        .andExpect(jsonPath("$.notificationInApp").value(true))
        .andExpect(jsonPath("$.notificationDesktop").value(false));

    assertThat(settingsRepository.findById(user.id())).isPresent();
  }

  @Test
  void patchSettings_shouldUpdateOnlyProvidedToggleAndPersist() throws Exception {
    RegisteredUser user = register("settings-patch@otterworks.dev");

    mockMvc
        .perform(
            patch("/api/v1/settings")
                .header("Authorization", user.bearer())
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"notificationDesktop\": true}"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.notificationEmail").value(true))
        .andExpect(jsonPath("$.notificationInApp").value(true))
        .andExpect(jsonPath("$.notificationDesktop").value(true));

    mockMvc
        .perform(
            patch("/api/v1/settings")
                .header("Authorization", user.bearer())
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"notificationEmail\": false}"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.notificationEmail").value(false))
        .andExpect(jsonPath("$.notificationDesktop").value(true));

    mockMvc
        .perform(get("/api/v1/settings").header("Authorization", user.bearer()))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.notificationEmail").value(false))
        .andExpect(jsonPath("$.notificationInApp").value(true))
        .andExpect(jsonPath("$.notificationDesktop").value(true));
  }

  @Test
  void patchSettings_shouldNotAffectOtherUsers() throws Exception {
    RegisteredUser alice = register("settings-alice@otterworks.dev");
    RegisteredUser bob = register("settings-bob@otterworks.dev");

    mockMvc
        .perform(
            patch("/api/v1/settings")
                .header("Authorization", alice.bearer())
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"notificationInApp\": false}"))
        .andExpect(status().isOk());

    mockMvc
        .perform(get("/api/v1/settings").header("Authorization", bob.bearer()))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.notificationInApp").value(true));
  }

  @Test
  void patchSettings_shouldRejectMalformedBody() throws Exception {
    RegisteredUser user = register("settings-malformed@otterworks.dev");

    mockMvc
        .perform(
            patch("/api/v1/settings")
                .header("Authorization", user.bearer())
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"notificationEmail\": \"not-a-boolean\"}"))
        .andExpect(status().isBadRequest());
  }

  @Test
  void settings_shouldRequireAuthentication() throws Exception {
    mockMvc.perform(get("/api/v1/settings")).andExpect(status().isForbidden());
    mockMvc
        .perform(
            patch("/api/v1/settings")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"notificationEmail\": false}"))
        .andExpect(status().isForbidden());
  }

  private RegisteredUser register(String email) throws Exception {
    String body =
        String.format(
            "{\"email\": \"%s\", \"password\": \"password123\", \"displayName\": \"Settings"
                + " User\"}",
            email);
    MvcResult result =
        mockMvc
            .perform(
                post("/api/v1/auth/register").contentType(MediaType.APPLICATION_JSON).content(body))
            .andExpect(status().isCreated())
            .andReturn();
    JsonNode json = objectMapper.readTree(result.getResponse().getContentAsString());
    return new RegisteredUser(
        UUID.fromString(json.get("user").get("id").asText()), json.get("accessToken").asText());
  }

  private record RegisteredUser(UUID id, String accessToken) {
    String bearer() {
      return "Bearer " + accessToken;
    }
  }
}
