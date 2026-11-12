package app.synthetic.insurance.iri;

public final class PolicyNumbers {
    private PolicyNumbers() {}

    public static long parse(String value) {
        if (value == null || !value.matches("[0-9]{1,30}")) {
            throw new IllegalArgumentException("Policy number must contain 1..30 digits");
        }
        try {
            return Long.parseLong(value);
        } catch (NumberFormatException error) {
            throw new IllegalArgumentException("Policy number exceeds the supported range", error);
        }
    }

    public static String canonical(String value) {
        return Long.toString(parse(value));
    }
}
