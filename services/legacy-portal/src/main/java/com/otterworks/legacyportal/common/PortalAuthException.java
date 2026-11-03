package com.otterworks.legacyportal.common;

import org.springframework.http.HttpStatus;

/** Raised when a request carries no valid identity (401) or the identity lacks access (403). */
public class PortalAuthException extends RuntimeException {

    public enum Kind {
        UNAUTHENTICATED(HttpStatus.UNAUTHORIZED),
        FORBIDDEN(HttpStatus.FORBIDDEN);

        private final HttpStatus status;

        Kind(HttpStatus status) {
            this.status = status;
        }

        public HttpStatus status() {
            return status;
        }
    }

    private final Kind kind;

    public PortalAuthException(Kind kind, String message) {
        super(message);
        this.kind = kind;
    }

    public Kind getKind() {
        return kind;
    }

    public HttpStatus getStatus() {
        return kind.status();
    }
}
