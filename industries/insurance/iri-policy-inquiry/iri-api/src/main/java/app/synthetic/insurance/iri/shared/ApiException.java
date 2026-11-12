package app.synthetic.insurance.iri.shared;

import org.springframework.http.HttpStatus;

public class ApiException extends RuntimeException {
    private final HttpStatus status;

    public ApiException(HttpStatus status, String message) {
        super(message);
        if (status != HttpStatus.BAD_REQUEST && status != HttpStatus.NOT_FOUND
                && status != HttpStatus.SERVICE_UNAVAILABLE) {
            throw new IllegalArgumentException("Unsupported inquiry error status");
        }
        this.status = status;
    }

    public HttpStatus status() {
        return status;
    }
}
