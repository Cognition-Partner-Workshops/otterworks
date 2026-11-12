package app.synthetic.insurance.iri;

import java.time.Instant;

public record ErrorBody(String code, String message, Instant timestamp) {}
