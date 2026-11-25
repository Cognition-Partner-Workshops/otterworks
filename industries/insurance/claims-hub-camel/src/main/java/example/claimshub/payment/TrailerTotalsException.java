package example.claimshub.payment;

/** The trailer guard refused a remittance file; nothing was sent. */
public class TrailerTotalsException extends Exception {

    public TrailerTotalsException(String message, Throwable cause) {
        super(message, cause);
    }
}
