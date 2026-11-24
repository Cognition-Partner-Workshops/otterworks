package example.claimshub.payment;

/** ClaimPayment.odx's VendorUnreachableException: every delivery attempt failed. */
public class VendorUnreachableException extends Exception {

    public VendorUnreachableException(String instructionId, int attempts, Throwable lastFailure) {
        super("payment " + instructionId + ": vendor unreachable after " + attempts + " attempts", lastFailure);
    }
}
