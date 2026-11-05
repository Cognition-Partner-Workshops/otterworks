package com.bank.kyc;

import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.boot.web.error.ErrorAttributeOptions;
import org.springframework.boot.web.servlet.error.DefaultErrorAttributes;
import org.springframework.stereotype.Component;
import org.springframework.web.context.request.WebRequest;

@Component
public class PublicErrorAttributes extends DefaultErrorAttributes {
    @Override
    public Map<String, Object> getErrorAttributes(WebRequest request, ErrorAttributeOptions options) {
        Map<String, Object> internal = super.getErrorAttributes(request, ErrorAttributeOptions.defaults());
        Map<String, Object> publicError = new LinkedHashMap<>();
        publicError.put("timestamp", internal.get("timestamp"));
        publicError.put("status", internal.get("status"));
        publicError.put("error", "Unable to complete request");
        return publicError;
    }
}
