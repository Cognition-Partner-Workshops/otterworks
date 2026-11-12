package app.synthetic.insurance.iri;

public class UnmappedValue extends RuntimeException {
    private final String code;

    public UnmappedValue(String message) {
        this("policy.status.unmapped", message);
    }

    public UnmappedValue(String code, String message) {
        super(message);
        this.code = code;
    }

    public String code() {
        return code;
    }
}
