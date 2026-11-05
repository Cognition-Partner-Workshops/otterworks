package com.bank.kyc;

import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.Date;
import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.boot.web.error.ErrorAttributeOptions;
import org.springframework.boot.webmvc.error.DefaultErrorAttributes;
import org.springframework.stereotype.Component;
import org.springframework.web.context.request.WebRequest;

@Component
public class PlatformErrorAttributes extends DefaultErrorAttributes {
    private static final DateTimeFormatter TIMESTAMP =
            DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss.SSSxxx").withZone(ZoneOffset.UTC);

    @Override
    public Map<String, Object> getErrorAttributes(WebRequest request, ErrorAttributeOptions options) {
        Map<String, Object> attributes = super.getErrorAttributes(request, options);
        Map<String, Object> ordered = new LinkedHashMap<>();
        attributes.forEach((key, value) -> {
            if ("path".equals(key)) ordered.putIfAbsent("message", "");
            ordered.put(key, "timestamp".equals(key) && value instanceof Date
                    ? TIMESTAMP.format(((Date) value).toInstant()) : value);
        });
        ordered.putIfAbsent("message", "");
        return ordered;
    }
}
