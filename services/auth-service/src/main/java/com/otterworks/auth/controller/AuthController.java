package com.otterworks.auth.controller;

import com.otterworks.auth.dto.*;
import com.otterworks.auth.service.AuthService;
import com.otterworks.auth.service.UserService;
import jakarta.validation.Valid;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/v1/auth")
public class AuthController {

  private final AuthService authService;
  private final UserService userService;
  private final Map<String, LookupWindow> lookupWindows = new HashMap<>();

  private record LookupWindow(long startedAt, int count) {}

  private synchronized void limitLookups(Authentication authentication) {
    long now = System.currentTimeMillis();
    lookupWindows.entrySet().removeIf(entry -> now - entry.getValue().startedAt() >= 60000);
    String caller = authentication.getName();
    LookupWindow window = lookupWindows.getOrDefault(caller, new LookupWindow(now, 0));
    if (window.count() >= 10 || (window.count() == 0 && lookupWindows.size() >= 10000)) {
      throw new ResponseStatusException(HttpStatus.TOO_MANY_REQUESTS, "Lookup limit reached");
    }
    lookupWindows.put(caller, new LookupWindow(window.startedAt(), window.count() + 1));
  }

  public AuthController(AuthService authService, UserService userService) {
    this.authService = authService;
    this.userService = userService;
  }

  @PostMapping("/register")
  public ResponseEntity<AuthResponse> register(@Valid @RequestBody RegisterRequest request) {
    AuthResponse response = authService.register(request);
    return ResponseEntity.status(HttpStatus.CREATED).body(response);
  }

  @PostMapping("/login")
  public ResponseEntity<AuthResponse> login(@Valid @RequestBody LoginRequest request) {
    AuthResponse response = authService.login(request);
    return ResponseEntity.ok(response);
  }

  @PostMapping("/refresh")
  public ResponseEntity<AuthResponse> refresh(@RequestHeader("Authorization") String bearerToken) {
    String token = bearerToken.replace("Bearer ", "");
    AuthResponse response = authService.refreshToken(token);
    return ResponseEntity.ok(response);
  }

  @GetMapping("/profile")
  public ResponseEntity<UserDTO> getProfile(Authentication authentication) {
    UUID userId = UUID.fromString((String) authentication.getPrincipal());
    UserDTO profile = userService.getProfile(userId);
    return ResponseEntity.ok(profile);
  }

  @PutMapping("/profile")
  public ResponseEntity<UserDTO> updateProfile(
      Authentication authentication, @Valid @RequestBody UpdateProfileRequest request) {
    UUID userId = UUID.fromString((String) authentication.getPrincipal());
    UserDTO profile = userService.updateProfile(userId, request);
    return ResponseEntity.ok(profile);
  }

  @PostMapping("/change-password")
  public ResponseEntity<Void> changePassword(
      Authentication authentication, @Valid @RequestBody ChangePasswordRequest request) {
    UUID userId = UUID.fromString((String) authentication.getPrincipal());
    authService.changePassword(userId, request);
    return ResponseEntity.noContent().build();
  }

  @GetMapping("/users/lookup")
  public ResponseEntity<UserLookupResponse> lookupUser(
      @RequestParam String email, Authentication authentication) {
    limitLookups(authentication);
    if (email.length() > 254 || !email.matches("[^\\s@]+@[^\\s@]+\\.[^\\s@]+")) {
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Exact email required");
    }
    UserDTO user = userService.findByEmail(email);
    return ResponseEntity.ok(new UserLookupResponse(user.getId(), null, null));
  }

  @GetMapping("/users/by-id/{id}")
  public ResponseEntity<UserLookupResponse> lookupUserById(
      @PathVariable UUID id, Authentication authentication) {
    limitLookups(authentication);
    boolean admin =
        authentication.getAuthorities().stream()
            .anyMatch(authority -> authority.getAuthority().equals("ROLE_ADMIN"));
    if (!id.toString().equals(authentication.getName()) && !admin) {
      throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Own profile only");
    }
    UserDTO user = userService.getProfile(id);
    return ResponseEntity.ok(UserLookupResponse.fromUserDTO(user));
  }

  @GetMapping("/users")
  @PreAuthorize("hasRole('ADMIN')")
  public ResponseEntity<Page<UserDTO>> listUsers(Pageable pageable) {
    Page<UserDTO> users = userService.listUsers(pageable);
    return ResponseEntity.ok(users);
  }

  @PostMapping("/logout")
  public ResponseEntity<Void> logout(Authentication authentication) {
    UUID userId = UUID.fromString((String) authentication.getPrincipal());
    authService.logout(userId);
    return ResponseEntity.noContent().build();
  }
}
