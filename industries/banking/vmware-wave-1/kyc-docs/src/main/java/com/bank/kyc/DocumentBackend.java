package com.bank.kyc;

import java.io.IOException;
import java.io.InputStream;
import java.util.List;

/** Where uploaded documents live. Names are validated by {@link DocumentStore}. */
public interface DocumentBackend {

    /** Stores {@code body} as {@code customer/name}, replacing any existing object, and returns its size. */
    long put(String customer, String name, InputStream body) throws IOException;

    /** Names stored for {@code customer}, in no particular order; empty when there are none. */
    List<String> list(String customer) throws IOException;

    /** Throws when the backend cannot take traffic. */
    void check() throws Exception;
}
