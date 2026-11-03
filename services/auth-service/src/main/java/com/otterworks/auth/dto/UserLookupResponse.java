package com.otterworks.auth.dto;

import lombok.AllArgsConstructor;
import lombok.Data;

/**
 * Minimal public view of a user for the file-sharing UI. Deliberately excludes email, roles and
 * timestamps: these endpoints are reachable by any authenticated user, so anything beyond id and
 * displayName would let one account harvest PII for the whole directory.
 */
@Data
@AllArgsConstructor
public class UserLookupResponse {
  private String id;
  private String displayName;

  public static UserLookupResponse fromUserDTO(UserDTO dto) {
    return new UserLookupResponse(dto.getId(), dto.getDisplayName());
  }
}
