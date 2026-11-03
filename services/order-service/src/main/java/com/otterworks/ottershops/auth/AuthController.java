package com.otterworks.ottershops.auth;

import com.otterworks.ottershops.bag.BagService;
import com.otterworks.ottershops.common.ApiException;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseCookie;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.UUID;

@RestController
@RequestMapping("/api/auth")
public class AuthController {
    private final AuthService auth;
    private final CurrentCustomer current;
    private final BagService bags;

    public AuthController(AuthService auth, CurrentCustomer current, BagService bags) {
        this.auth = auth;
        this.current = current;
        this.bags = bags;
    }

    public record RegisterRequest(String email, String password, String firstName, String lastName, UUID bagId) {}
    public record LoginRequest(String email, String password, UUID bagId) {}
    public record SessionResponse(Customer customer, UUID bagId) {}

    @PostMapping("/register")
    public ResponseEntity<SessionResponse> register(@RequestBody RegisterRequest req) {
        Customer c = auth.register(req.email(), req.password(), req.firstName(), req.lastName());
        String token = auth.startSession(c.id());
        UUID bagId = bags.claim(req.bagId(), c.id());
        return withCookie(ResponseEntity.status(HttpStatus.CREATED), token, AuthService.SESSION_TTL.toSeconds())
                .body(new SessionResponse(c, bagId));
    }

    @PostMapping("/login")
    public ResponseEntity<SessionResponse> login(@RequestBody LoginRequest req) {
        AuthService.Session s = auth.login(req.email(), req.password());
        UUID bagId = bags.claim(req.bagId(), s.customer().id());
        return withCookie(ResponseEntity.ok(), s.token(), AuthService.SESSION_TTL.toSeconds())
                .body(new SessionResponse(s.customer(), bagId));
    }

    @PostMapping("/logout")
    public ResponseEntity<Void> logout(HttpServletRequest req) {
        auth.logout(CurrentCustomer.token(req));
        return withCookie(ResponseEntity.status(HttpStatus.NO_CONTENT), "", 0).build();
    }

    @GetMapping("/me")
    public SessionResponse me(HttpServletRequest req) {
        Customer c = current.get(req).orElseThrow(ApiException::unauthorized);
        return new SessionResponse(c, bags.openBagFor(c.id()).orElse(null));
    }

    private static ResponseEntity.BodyBuilder withCookie(ResponseEntity.BodyBuilder b, String token, long maxAge) {
        ResponseCookie cookie = ResponseCookie.from(CurrentCustomer.COOKIE, token)
                .httpOnly(true).sameSite("Lax").path("/").maxAge(maxAge).build();
        return b.header(HttpHeaders.SET_COOKIE, cookie.toString());
    }
}
