package com.otterworks.auth.qa;

import static org.assertj.core.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.otterworks.auth.repository.RefreshTokenRepository;
import com.otterworks.auth.repository.UserRepository;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Disabled;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

/** QA coverage for registration, login, refresh, logout and password validation. */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class AuthQaIntegrationTest {

  private static final String PASSWORD = "QaPassw0rd!";

  @Autowired private MockMvc mockMvc;
  @Autowired private ObjectMapper objectMapper;
  @Autowired private UserRepository userRepository;
  @Autowired private RefreshTokenRepository refreshTokenRepository;

  @BeforeEach
  void setUp() {
    refreshTokenRepository.deleteAll();
    userRepository.deleteAll();
  }

  private JsonNode register(String email, String password) throws Exception {
    String body =
        objectMapper.writeValueAsString(
            Map.of("email", email, "password", password, "displayName", "QA User"));
    String response =
        mockMvc
            .perform(
                post("/api/v1/auth/register").contentType(MediaType.APPLICATION_JSON).content(body))
            .andExpect(status().isCreated())
            .andReturn()
            .getResponse()
            .getContentAsString();
    return objectMapper.readTree(response);
  }

  private int registerStatus(String password) throws Exception {
    String body =
        objectMapper.writeValueAsString(
            Map.of("email", "pw@otterworks.dev", "password", password, "displayName", "QA"));
    return mockMvc
        .perform(
            post("/api/v1/auth/register").contentType(MediaType.APPLICATION_JSON).content(body))
        .andReturn()
        .getResponse()
        .getStatus();
  }

  private int loginStatus(String email, String password) throws Exception {
    String body = objectMapper.writeValueAsString(Map.of("email", email, "password", password));
    return mockMvc
        .perform(post("/api/v1/auth/login").contentType(MediaType.APPLICATION_JSON).content(body))
        .andReturn()
        .getResponse()
        .getStatus();
  }

  @Test
  void passwordLength_boundariesAreEnforced() throws Exception {
    assertThat(registerStatus("a".repeat(7))).isEqualTo(400);
    assertThat(registerStatus("a".repeat(129))).isEqualTo(400);
    assertThat(registerStatus("a".repeat(8))).isEqualTo(201);
  }

  @Test
  void register_rejectsBlankDisplayNameAndMissingFields() throws Exception {
    mockMvc
        .perform(
            post("/api/v1/auth/register")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"email\":\"a@otterworks.dev\",\"password\":\"password123\"}"))
        .andExpect(status().isBadRequest())
        .andExpect(
            jsonPath("$.message").value(org.hamcrest.Matchers.containsString("displayName")));
  }

  @Test
  void register_doesNotLeakPasswordHash() throws Exception {
    JsonNode tokens = register("nohash@otterworks.dev", PASSWORD);
    assertThat(tokens.toString()).doesNotContain("passwordHash").doesNotContain(PASSWORD);
  }

  @Test
  void login_wrongPasswordAndUnknownUserReturnSameStatus() throws Exception {
    register("known@otterworks.dev", PASSWORD);
    assertThat(loginStatus("known@otterworks.dev", "wrong-password")).isEqualTo(400);
    assertThat(loginStatus("unknown@otterworks.dev", "wrong-password")).isEqualTo(400);
  }

  @Test
  void refreshToken_isRejectedAsAccessTokenByAuthService() throws Exception {
    JsonNode tokens = register("refresh-as-access@otterworks.dev", PASSWORD);
    mockMvc
        .perform(
            get("/api/v1/auth/profile")
                .header("Authorization", "Bearer " + tokens.get("refreshToken").asText()))
        .andExpect(status().isForbidden());
  }

  @Test
  void accessToken_isRejectedByRefreshEndpoint() throws Exception {
    JsonNode tokens = register("access-as-refresh@otterworks.dev", PASSWORD);
    mockMvc
        .perform(
            post("/api/v1/auth/refresh")
                .header("Authorization", "Bearer " + tokens.get("accessToken").asText()))
        .andExpect(status().isBadRequest());
  }

  @Test
  void refreshToken_rotationRevokesPreviousToken() throws Exception {
    JsonNode tokens = register("rotate@otterworks.dev", PASSWORD);
    String oldRefresh = tokens.get("refreshToken").asText();
    mockMvc
        .perform(post("/api/v1/auth/refresh").header("Authorization", "Bearer " + oldRefresh))
        .andExpect(status().isOk());
    mockMvc
        .perform(post("/api/v1/auth/refresh").header("Authorization", "Bearer " + oldRefresh))
        .andExpect(status().isBadRequest());
  }

  @Test
  void logout_revokesRefreshTokens() throws Exception {
    JsonNode tokens = register("logout@otterworks.dev", PASSWORD);
    mockMvc
        .perform(
            post("/api/v1/auth/logout")
                .header("Authorization", "Bearer " + tokens.get("accessToken").asText()))
        .andExpect(status().isNoContent());
    mockMvc
        .perform(
            post("/api/v1/auth/refresh")
                .header("Authorization", "Bearer " + tokens.get("refreshToken").asText()))
        .andExpect(status().isBadRequest());
  }

  @Test
  void logout_withoutTokenIsRejected() throws Exception {
    int status = mockMvc.perform(post("/api/v1/auth/logout")).andReturn().getResponse().getStatus();
    assertThat(status).isIn(401, 403);
  }

  @Test
  void changePassword_revokesRefreshTokensAndOldPasswordStopsWorking() throws Exception {
    JsonNode tokens = register("chpw@otterworks.dev", PASSWORD);
    String body =
        objectMapper.writeValueAsString(
            Map.of("currentPassword", PASSWORD, "newPassword", "NewPassw0rd!"));
    mockMvc
        .perform(
            post("/api/v1/auth/change-password")
                .header("Authorization", "Bearer " + tokens.get("accessToken").asText())
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
        .andExpect(status().isNoContent());
    assertThat(loginStatus("chpw@otterworks.dev", PASSWORD)).isEqualTo(400);
    assertThat(loginStatus("chpw@otterworks.dev", "NewPassw0rd!")).isEqualTo(200);
    mockMvc
        .perform(
            post("/api/v1/auth/refresh")
                .header("Authorization", "Bearer " + tokens.get("refreshToken").asText()))
        .andExpect(status().isBadRequest());
  }

  @Test
  @Disabled("[REAL] auth-email-case: emails are stored/compared case-sensitively")
  void login_isCaseInsensitiveOnEmail() throws Exception {
    register("CaseUser@otterworks.dev", PASSWORD);
    assertThat(loginStatus("caseuser@otterworks.dev", PASSWORD)).isEqualTo(200);
  }

  @Test
  @Disabled("[REAL] auth-email-case: same address with different case registers a second account")
  void register_rejectsDuplicateEmailDifferingOnlyInCase() throws Exception {
    register("dup@otterworks.dev", PASSWORD);
    String body =
        objectMapper.writeValueAsString(
            Map.of("email", "DUP@otterworks.dev", "password", PASSWORD, "displayName", "QA"));
    mockMvc
        .perform(
            post("/api/v1/auth/register").contentType(MediaType.APPLICATION_JSON).content(body))
        .andExpect(status().isBadRequest());
  }

  @Test
  @Disabled("[REAL] auth-malformed-500: malformed JSON body returns 500 instead of 400")
  void login_malformedJsonReturns400() throws Exception {
    mockMvc
        .perform(post("/api/v1/auth/login").contentType(MediaType.APPLICATION_JSON).content("{"))
        .andExpect(status().isBadRequest());
  }

  @Test
  @Disabled("[REAL] auth-malformed-500: /refresh without Authorization header returns 500")
  void refresh_missingHeaderReturns4xx() throws Exception {
    int status =
        mockMvc.perform(post("/api/v1/auth/refresh")).andReturn().getResponse().getStatus();
    assertThat(status).isBetween(400, 499);
  }

  @Test
  void refresh_garbageTokenReturns401() throws Exception {
    mockMvc
        .perform(post("/api/v1/auth/refresh").header("Authorization", "Bearer not-a-jwt"))
        .andExpect(status().isUnauthorized());
  }

  @Test
  @Disabled("[REAL] auth-malformed-500: empty or non-JSON login body returns 500 instead of 400")
  void login_wrongContentTypeReturns4xx() throws Exception {
    int status =
        mockMvc
            .perform(post("/api/v1/auth/login").contentType(MediaType.TEXT_PLAIN).content("x"))
            .andReturn()
            .getResponse()
            .getStatus();
    assertThat(status).isBetween(400, 499);
  }
}
