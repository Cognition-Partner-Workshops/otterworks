package app.synthetic.insurance.iri;

import java.time.Instant;
import org.springframework.dao.DataAccessException;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class InquiryAdvice {
    private ResponseEntity<ErrorBody> error(int status, String code, String message) {
        return ResponseEntity.status(status).body(new ErrorBody(code, message, Instant.now()));
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<ErrorBody> invalid(IllegalArgumentException exception) {
        return error(400, "policy.inquiry.invalidPolicyNumber", exception.getMessage());
    }

    @ExceptionHandler(DataAccessException.class)
    public ResponseEntity<ErrorBody> unavailable(DataAccessException exception) {
        return error(503, "policy.inquiry.unavailable", "Policy inquiry is unavailable");
    }

    @ExceptionHandler(NotFound.class)
    public ResponseEntity<ErrorBody> notFound(NotFound exception) {
        return error(404, "policy.inquiry.notFound", exception.getMessage());
    }

    @ExceptionHandler(UnmappedValue.class)
    public ResponseEntity<ErrorBody> unmapped(UnmappedValue exception) {
        return error(422, exception.code(), exception.getMessage());
    }
}
