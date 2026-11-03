package com.otterworks.ottershops.ops;

import com.otterworks.ottershops.common.ApiException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;

@Component
public class OpsAuth {
    private final String opsKey;

    public OpsAuth(@Value("${ottershops.ops.api-key:}") String opsKey) {
        this.opsKey = opsKey;
    }

    public void check(String key) {
        if (opsKey.isBlank() || key == null
                || !MessageDigest.isEqual(opsKey.getBytes(StandardCharsets.UTF_8), key.getBytes(StandardCharsets.UTF_8))) {
            throw new ApiException(HttpStatus.FORBIDDEN, "FORBIDDEN", "Ops key required");
        }
    }
}
