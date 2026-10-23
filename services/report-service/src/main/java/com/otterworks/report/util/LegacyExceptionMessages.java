package com.otterworks.report.util;

import org.springframework.core.NestedCheckedException;
import org.springframework.core.NestedRuntimeException;

import java.util.Objects;

/**
 * Reproduces Spring 5 nested exception messages so stored report errors stay identical across the Boot 3 upgrade.
 */
public final class LegacyExceptionMessages {

    private LegacyExceptionMessages() {
    }

    public static String message(Throwable t) {
        if (t == null) return null;
        Throwable cause = t.getCause();
        if (cause == null || cause == t) return t.getMessage();
        if (t instanceof NestedRuntimeException || t instanceof NestedCheckedException) {
            StringBuilder sb = new StringBuilder(64);
            if (t.getMessage() != null) sb.append(t.getMessage()).append("; ");
            sb.append("nested exception is ").append(describe(cause));
            return sb.toString();
        }
        if (Objects.equals(t.getMessage(), cause.toString())) return describe(cause);
        return t.getMessage();
    }

    static String describe(Throwable t) {
        String msg = message(t);
        return msg != null ? t.getClass().getName() + ": " + msg : t.getClass().getName();
    }
}
