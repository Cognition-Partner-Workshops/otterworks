package app.synthetic.insurance.iri.shared;

import java.time.Instant;
import org.springframework.dao.DataAccessException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.servlet.NoHandlerFoundException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

@RestControllerAdvice
public class GlobalErrorHandler {
    @ExceptionHandler(ApiException.class)
    public ResponseEntity<ApiError> api(ApiException error) {
        return response(error.status(), error.getMessage());
    }

    @ExceptionHandler({IllegalArgumentException.class, MethodArgumentTypeMismatchException.class,
            MissingServletRequestParameterException.class, HttpMessageNotReadableException.class})
    public ResponseEntity<ApiError> badRequest(Exception error) {
        return response(HttpStatus.BAD_REQUEST, "Invalid inquiry request");
    }

    @ExceptionHandler({NoResourceFoundException.class, NoHandlerFoundException.class})
    public ResponseEntity<ApiError> notFound(Exception error) {
        return response(HttpStatus.NOT_FOUND, "Policy inquiry resource not found");
    }

    @ExceptionHandler(DataAccessException.class)
    public ResponseEntity<ApiError> unavailable(DataAccessException error) {
        return response(HttpStatus.SERVICE_UNAVAILABLE, "Policy inquiry data unavailable");
    }

    private ResponseEntity<ApiError> response(HttpStatus status, String message) {
        String category = switch (status) {
            case BAD_REQUEST -> "Invalid";
            case NOT_FOUND -> "NotFound";
            default -> "Unavailable";
        };
        return ResponseEntity.status(status).body(new ApiError("Inquiry.Request." + category, message, Instant.now()));
    }
}
