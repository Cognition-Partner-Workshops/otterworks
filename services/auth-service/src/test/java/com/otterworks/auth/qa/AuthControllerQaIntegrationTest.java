package com.otterworks.auth.qa;

import static org.assertj.core.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.otterworks.auth.repository.RefreshTokenRepository;
import com.otterworks.auth.repository.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class AuthControllerQaIntegrationTest {

  private static final String PASSWORD = "OtterworksTest123!";

  @Autowired private MockMvc mockMvc;
  @Autowired private ObjectMapper objectMapper;
  @Autowired private UserRepository userRepository;
  @Autowired private RefreshTokenRepository refreshTokenRepository;

  @BeforeEach
  void setUp() {
    refreshTokenRepository.deleteAll();
    userRepository.deleteAll();
  }

  private ResultActions postJson(String path, String body) throws Exception {
    return mockMvc.perform(post(path).contentType(MediaType.APPLICATION_JSON).content(body));
  }

  private JsonNode register(String email, String password) throws Exception {
    String body =
        objectMapper.writeValueAsString(
            java.util.Map.of("email", email, "password", password, "displayName", "QA"));
    String json =
        postJson("/api/v1/auth/register", body)
            .andExpect(status().isCreated())
            .andReturn()
            .getResponse()
            .getContentAsString();
    return objectMapper.readTree(json);
  }

  private ResultActions login(String email, String password) throws Exception {
    return postJson(
        "/api/v1/auth/login",
        objectMapper.writeValueAsString(java.util.Map.of("email", email, "password", password)));
  }

  private ResultActions refresh(String token) throws Exception {
    return mockMvc.perform(post("/api/v1/auth/refresh").header("Authorization", "Bearer " + token));
  }

  @Test
  void authResponsesNeverExposePasswordMaterial() throws Exception {
    String registerJson = register("leak@otterworks.dev", PASSWORD).toString();
    String loginJson =
        login("leak@otterworks.dev", PASSWORD).andReturn().getResponse().getContentAsString();
    for (String json : new String[] {registerJson, loginJson}) {
      assertThat(json).doesNotContainIgnoringCase("passwordHash").doesNotContain(PASSWORD);
    }
  }

  @Test
  void loginErrorDoesNotRevealWhetherTheAccountExists() throws Exception {
    register("known@otterworks.dev", PASSWORD);
    String wrongPassword =
        login("known@otterworks.dev", "WrongPassword1!")
            .andExpect(status().isBadRequest())
            .andReturn()
            .getResponse()
            .getContentAsString();
    String unknownUser =
        login("unknown@otterworks.dev", "WrongPassword1!")
            .andExpect(status().isBadRequest())
            .andReturn()
            .getResponse()
            .getContentAsString();
    assertThat(objectMapper.readTree(wrongPassword).get("message"))
        .isEqualTo(objectMapper.readTree(unknownUser).get("message"));
  }

  @Test
  void registerRejectsShortPasswordAndBlankName() throws Exception {
    postJson(
            "/api/v1/auth/register",
            "{\"email\":\"a@otterworks.dev\",\"password\":\"short\",\"displayName\":\"A\"}")
        .andExpect(status().isBadRequest());
    postJson(
            "/api/v1/auth/register",
            "{\"email\":\"b@otterworks.dev\",\"password\":\""
                + PASSWORD
                + "\",\"displayName\":\" \"}")
        .andExpect(status().isBadRequest());
    assertThat(userRepository.count()).isZero();
  }

  @Test
  void registerRejectsPasswordLongerThan128Characters() throws Exception {
    String longPassword = "A".repeat(129);
    postJson(
            "/api/v1/auth/register",
            "{\"email\":\"c@otterworks.dev\",\"password\":\""
                + longPassword
                + "\",\"displayName\":\"C\"}")
        .andExpect(status().isBadRequest());
  }

  @Test
  void loginRejectsBlankPassword() throws Exception {
    postJson("/api/v1/auth/login", "{\"email\":\"a@otterworks.dev\",\"password\":\"\"}")
        .andExpect(status().isBadRequest());
  }

  @Test
  void refreshRotatesAndOldRefreshTokenCannotBeReplayed() throws Exception {
    JsonNode tokens = register("rotate@otterworks.dev", PASSWORD);
    String original = tokens.get("refreshToken").asText();
    String rotatedJson =
        refresh(original).andExpect(status().isOk()).andReturn().getResponse().getContentAsString();
    String rotated = objectMapper.readTree(rotatedJson).get("refreshToken").asText();

    refresh(original).andExpect(status().isBadRequest());
    refresh(rotated).andExpect(status().isOk());
  }

  @Test
  void refreshRejectsAnAccessToken() throws Exception {
    JsonNode tokens = register("access-as-refresh@otterworks.dev", PASSWORD);
    refresh(tokens.get("accessToken").asText())
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.message").value("Token is not a refresh token"));
  }

  @Test
  void refreshRejectsAGarbageToken() throws Exception {
    refresh("not.a.jwt").andExpect(status().isUnauthorized());
  }

  @Test
  void refreshTokenCannotBeUsedAsABearerOnProtectedAuthRoutes() throws Exception {
    JsonNode tokens = register("refresh-as-bearer@otterworks.dev", PASSWORD);
    mockMvc
        .perform(
            get("/api/v1/auth/profile")
                .header("Authorization", "Bearer " + tokens.get("refreshToken").asText()))
        .andExpect(status().isForbidden());
  }

  @Test
  void logoutRevokesEveryRefreshTokenOfTheUser() throws Exception {
    JsonNode first = register("logout@otterworks.dev", PASSWORD);
    JsonNode second =
        objectMapper.readTree(
            login("logout@otterworks.dev", PASSWORD)
                .andReturn()
                .getResponse()
                .getContentAsString());

    mockMvc
        .perform(
            post("/api/v1/auth/logout")
                .header("Authorization", "Bearer " + second.get("accessToken").asText()))
        .andExpect(status().isNoContent());

    refresh(first.get("refreshToken").asText()).andExpect(status().isBadRequest());
    refresh(second.get("refreshToken").asText()).andExpect(status().isBadRequest());
  }

  @Test
  void logoutWithoutTokenIsRejected() throws Exception {
    mockMvc.perform(post("/api/v1/auth/logout")).andExpect(status().isForbidden());
  }

  @Test
  void changePasswordRevokesRefreshTokensAndSwapsCredentials() throws Exception {
    JsonNode tokens = register("rotate-pw@otterworks.dev", PASSWORD);
    mockMvc
        .perform(
            post("/api/v1/auth/change-password")
                .header("Authorization", "Bearer " + tokens.get("accessToken").asText())
                .contentType(MediaType.APPLICATION_JSON)
                .content(
                    "{\"currentPassword\":\"" + PASSWORD + "\",\"newPassword\":\"BrandNew123!\"}"))
        .andExpect(status().isNoContent());

    refresh(tokens.get("refreshToken").asText()).andExpect(status().isBadRequest());
    login("rotate-pw@otterworks.dev", PASSWORD).andExpect(status().isBadRequest());
    login("rotate-pw@otterworks.dev", "BrandNew123!").andExpect(status().isOk());
  }

  @Test
  void changePasswordWithWrongCurrentPasswordIsRejected() throws Exception {
    JsonNode tokens = register("wrong-current@otterworks.dev", PASSWORD);
    mockMvc
        .perform(
            post("/api/v1/auth/change-password")
                .header("Authorization", "Bearer " + tokens.get("accessToken").asText())
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"currentPassword\":\"Nope12345!\",\"newPassword\":\"BrandNew123!\"}"))
        .andExpect(status().isBadRequest());
    login("wrong-current@otterworks.dev", PASSWORD).andExpect(status().isOk());
  }

  @Test
  void tamperedAccessTokenIsRejected() throws Exception {
    String access = register("tamper@otterworks.dev", PASSWORD).get("accessToken").asText();
    String tampered = access.substring(0, access.length() - 4) + "AAAA";
    mockMvc
        .perform(get("/api/v1/auth/profile").header("Authorization", "Bearer " + tampered))
        .andExpect(status().isForbidden());
  }

  // ---- [REAL] defects found during QA: these intentionally stay failing on main ----

  @Test
  @DisplayName("[REAL] login with malformed JSON body should be 400, not 500")
  void loginWithMalformedBodyIsAClientError() throws Exception {
    postJson("/api/v1/auth/login", "{bad").andExpect(status().isBadRequest());
  }

  @Test
  @DisplayName("[REAL] login with no body should be 400, not 500")
  void loginWithEmptyBodyIsAClientError() throws Exception {
    mockMvc
        .perform(post("/api/v1/auth/login").contentType(MediaType.APPLICATION_JSON))
        .andExpect(status().isBadRequest());
  }

  @Test
  @DisplayName("[REAL] refresh without Authorization header should be 4xx, not 500")
  void refreshWithoutHeaderIsAClientError() throws Exception {
    mockMvc
        .perform(post("/api/v1/auth/refresh"))
        .andExpect(result -> assertThat(result.getResponse().getStatus()).isBetween(400, 499));
  }

  @Test
  @DisplayName("[REAL] email addresses should be case-insensitive for login")
  void loginEmailIsCaseInsensitive() throws Exception {
    register("Mixed.Case@OtterWorks.dev", PASSWORD);
    login("mixed.case@otterworks.dev", PASSWORD).andExpect(status().isOk());
  }

  @Test
  @DisplayName("[REAL] registering the same mailbox with different case should be rejected")
  void registerEmailUniquenessIsCaseInsensitive() throws Exception {
    register("Dup.Case@OtterWorks.dev", PASSWORD);
    postJson(
            "/api/v1/auth/register",
            "{\"email\":\"dup.case@otterworks.dev\",\"password\":\""
                + PASSWORD
                + "\",\"displayName\":\"Dup\"}")
        .andExpect(status().isBadRequest());
  }

  @Test
  @DisplayName("[REAL] passwords over bcrypt's 72-byte limit must not match on prefix only")
  void longPasswordsAreNotSilentlyTruncated() throws Exception {
    String prefix = "A".repeat(72);
    register("long-pw@otterworks.dev", prefix + "OriginalTail1!");
    login("long-pw@otterworks.dev", prefix + "CompletelyDifferent")
        .andExpect(status().isBadRequest());
  }
}
