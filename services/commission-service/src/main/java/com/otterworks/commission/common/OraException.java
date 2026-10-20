package com.otterworks.commission.common;

/**
 * A rejection the legacy package raised with RAISE_APPLICATION_ERROR. The code is
 * negative (-20001 .. -20008) and the message is the exact text callers of
 * COMMISSION_PKG saw; the package delegate re-raises both unchanged.
 */
public class OraException extends RuntimeException {

    private final int oraCode;

    public OraException(int oraCode, String message) {
        super(message);
        this.oraCode = oraCode;
    }

    public int oraCode() {
        return oraCode;
    }
}
