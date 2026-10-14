package com.otterworks.auth.qa;

import static org.assertj.core.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.otterworks.auth.entity.User;
import com.otterworks.auth.repository.RefreshTokenRepository;
import com.otterworks.auth.repository.UserRepository;
import com.otterworks.auth.security.JwtTokenProvider;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class QaAuthHttpContractTest {

  private static final String SECRET =
      "test-jwt-secret-otterworks-must-be-at-least-32-bytes-long-for-hmac";

  @Autowired private MockMvc mockMvc;
  @Autowired private ObjectMapper objectMapper;
  @Autowired private UserRepository userRepository;
  @Autowired private RefreshTokenRepository refreshTokenRepository;

  @BeforeEach
  void setUp() {
    refreshTokenRepository.deleteAll();
    userRepository.deleteAll();
  }

  private JsonNode register(String email) throws Exception {
    String body =
        "{\"email\":\"" + email + "\",\"password\":\"Passw0rd!23\",\"displayName\":\"QA\"}";
    String res =
        mockMvc
            .perform(post("/api/v1/auth/register").contentType(MediaType.APPLICATION_JSON).content(body))
            .andExpect(status().isCreated())
            .andReturn()
            .getResponse()
            .getContentAsString();
    return objectMapper.readTree(res);
  }

  private User userFor(String email) {
    return userRepository.findByEmail(email).orElseThrow();
  }

  @Test
  void register_doesNotLeakPasswordHash() throws Exception {
    JsonNode res = register("leak@otterworks.dev");
    assertThat(res.toString()).doesNotContain("passwordHash").doesNotContain("Passw0rd!23");
  }

  @Test
  void login_wrongPassword_returnsGeneric4xx() throws Exception {
    register("wrong@otterworks.dev");
    mockMvc
        .perform(
            post("/api/v1/auth/login")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"email\":\"wrong@otterworks.dev\",\"password\":\"nope-nope\"}"))
        .andExpect(status().is4xxClientError())
        .andExpect(jsonPath("$.accessToken").doesNotExist());
  }

  @Test
  void login_missingBody_is4xx() throws Exception {
    mockMvc
        .perform(post("/api/v1/auth/login").contentType(MediaType.APPLICATION_JSON).content("{}"))
        .andExpect(status().isBadRequest());
  }

  @Test
  void profile_withExpiredAccessToken_isRejected() throws Exception {
    register("expired@otterworks.dev");
    String expired =
        new JwtTokenProvider(SECRET, -5, -5).generateAccessToken(userFor("expired@otterworks.dev"));
    mockMvc
        .perform(get("/api/v1/auth/profile").header("Authorization", "Bearer " + expired))
        .andExpect(status().is4xxClientError());
  }

  @Test
  void profile_withRefreshTokenAsBearer_isRejected() throws Exception {
    JsonNode res = register("asbearer@otterworks.dev");
    mockMvc
        .perform(
            get("/api/v1/auth/profile")
                .header("Authorization", "Bearer " + res.get("refreshToken").asText()))
        .andExpect(status().is4xxClientError());
  }

  @Test
  void profile_withForeignSignedToken_isRejected() throws Exception {
    register("foreign@otterworks.dev");
    String foreign =
        new JwtTokenProvider("another-secret-otterworks-that-is-also-at-least-32-bytes-long", 60, 60)
            .generateAccessToken(userFor("foreign@otterworks.dev"));
    mockMvc
        .perform(get("/api/v1/auth/profile").header("Authorization", "Bearer " + foreign))
        .andExpect(status().is4xxClientError());
  }

  @Test
  void refresh_withoutAuthorizationHeader_is4xx() throws Exception {
    mockMvc.perform(post("/api/v1/auth/refresh")).andExpect(status().is4xxClientError());
  }

  @Test
  void refresh_withExpiredRefreshToken_isUnauthorized() throws Exception {
    register("exprefresh@otterworks.dev");
    String expired =
        new JwtTokenProvider(SECRET, -5, -5).generateRefreshToken(userFor("exprefresh@otterworks.dev"));
    mockMvc
        .perform(post("/api/v1/auth/refresh").header("Authorization", "Bearer " + expired))
        .andExpect(status().isUnauthorized());
  }

  @Test
  void refresh_withAccessToken_isRejected() throws Exception {
    JsonNode res = register("accrefresh@otterworks.dev");
    mockMvc
        .perform(
            post("/api/v1/auth/refresh")
                .header("Authorization", "Bearer " + res.get("accessToken").asText()))
        .andExpect(status().is4xxClientError());
  }

  @Test
  void logout_revokesRefreshToken() throws Exception {
    JsonNode res = register("logout@otterworks.dev");
    mockMvc
        .perform(
            post("/api/v1/auth/logout")
                .header("Authorization", "Bearer " + res.get("accessToken").asText()))
        .andExpect(status().is2xxSuccessful());
    mockMvc
        .perform(
            post("/api/v1/auth/refresh")
                .header("Authorization", "Bearer " + res.get("refreshToken").asText()))
        .andExpect(status().is4xxClientError());
  }

  @Test
  void logout_withoutToken_isRejected() throws Exception {
    mockMvc.perform(post("/api/v1/auth/logout")).andExpect(status().is4xxClientError());
  }

  @Test
  void regularUser_cannotListUsers() throws Exception {
    JsonNode res = register("plain@otterworks.dev");
    mockMvc
        .perform(
            get("/api/v1/auth/users")
                .header("Authorization", "Bearer " + res.get("accessToken").asText()))
        .andExpect(status().isForbidden());
  }
}
