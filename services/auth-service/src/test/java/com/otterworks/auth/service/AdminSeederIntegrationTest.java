package com.otterworks.auth.service;

import static org.assertj.core.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import com.otterworks.auth.entity.User;
import com.otterworks.auth.repository.UserRepository;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest(
    properties = {
      "spring.datasource.url=jdbc:h2:mem:seedtestdb;MODE=PostgreSQL;DB_CLOSE_DELAY=-1;DATABASE_TO_LOWER=TRUE",
      "auth.seed-admin.email=seeded-admin@otterworks.dev",
      "auth.seed-admin.password=seeded-admin-password"
    })
@AutoConfigureMockMvc
@ActiveProfiles("test")
class AdminSeederIntegrationTest {

  @Autowired private MockMvc mockMvc;
  @Autowired private UserRepository userRepository;

  @Test
  void seededAdmin_isStoredAsBcryptAndCanLogIn() throws Exception {
    User admin = userRepository.findByEmail("seeded-admin@otterworks.dev").orElseThrow();
    assertThat(admin.getPasswordHash()).startsWith("$2a$").doesNotContain("seeded-admin-password");
    assertThat(admin.getRoles()).contains(User.Role.ADMIN, User.Role.USER);

    String body =
        """
        {"email": "seeded-admin@otterworks.dev", "password": "seeded-admin-password"}
        """;
    mockMvc
        .perform(post("/api/v1/auth/login").contentType(MediaType.APPLICATION_JSON).content(body))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.user.email").value("seeded-admin@otterworks.dev"));
  }
}
