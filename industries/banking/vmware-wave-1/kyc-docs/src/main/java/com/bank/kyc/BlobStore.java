package com.bank.kyc;

import java.io.IOException;
import java.io.InputStream;
import java.util.List;

public interface BlobStore {
    long put(String key, InputStream body, long size) throws IOException;
    List<String> list(String customer) throws IOException;
    boolean healthy();
}
