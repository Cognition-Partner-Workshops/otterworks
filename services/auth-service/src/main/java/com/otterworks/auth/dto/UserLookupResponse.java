package com.otterworks.auth.dto;

import com.otterworks.auth.util.DisplayNames;
import lombok.AllArgsConstructor;
import lombok.Data;

@Data
@AllArgsConstructor
public class UserLookupResponse {
  private String id;
  private String email;
  private String displayName;
  private String initials;

  public static UserLookupResponse fromUserDTO(UserDTO dto) {
    return new UserLookupResponse(
        dto.getId(),
        dto.getEmail(),
        dto.getDisplayName(),
        DisplayNames.initials(dto.getDisplayName(), dto.getEmail()));
  }
}
