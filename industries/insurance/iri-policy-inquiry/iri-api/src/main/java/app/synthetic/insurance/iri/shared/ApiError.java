package app.synthetic.insurance.iri.shared;

import java.time.Instant;

public record ApiError(String code, String message, Instant timestamp) {}
