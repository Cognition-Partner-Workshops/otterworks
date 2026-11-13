package com.otterworks.auth.dto;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class UserLookupResponseTest {

  @Test
  void carriesInitialsForTheLookedUpUser() {
    UserDTO dto = new UserDTO();
    dto.setId("42");
    dto.setEmail("ada@otterworks.io");
    dto.setDisplayName("Ada Lovelace");

    UserLookupResponse response = UserLookupResponse.fromUserDTO(dto);

    assertThat(response.getDisplayName()).isEqualTo("Ada Lovelace");
    assertThat(response.getInitials()).isEqualTo("AL");
  }
}
