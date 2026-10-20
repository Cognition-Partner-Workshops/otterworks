package com.bank.kyc;

import jakarta.servlet.RequestDispatcher;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.boot.web.error.ErrorAttributeOptions;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.boot.webmvc.error.DefaultErrorAttributes;
import org.springframework.boot.webmvc.error.ErrorAttributes;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.Ordered;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ControllerAdvice;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.context.request.WebRequest;
import org.springframework.web.filter.UrlHandlerFilter;
import org.springframework.web.multipart.MaxUploadSizeExceededException;

/**
 * Keeps the HTTP contract of the Spring Boot 2.3 build (pinned by characterization/): trailing-slash
 * matching, an empty "message" in error bodies, and 500 (not 413) for uploads over the size limit.
 */
@Configuration
@ControllerAdvice
public class LegacyHttpBehaviour {

    private final ErrorAttributes errorAttributes = new DefaultErrorAttributes() {
        @Override
        public Map<String, Object> getErrorAttributes(WebRequest request, ErrorAttributeOptions options) {
            Map<String, Object> current = super.getErrorAttributes(request, options);
            Map<String, Object> out = new LinkedHashMap<>();
            for (String k : new String[] {"timestamp", "status", "error"}) {
                if (current.containsKey(k)) out.put(k, current.get(k));
            }
            out.put("message", "");
            current.forEach(out::putIfAbsent);
            return out;
        }
    };

    @Bean
    public ErrorAttributes errorAttributes() {
        return errorAttributes;
    }

    /** Spring 7 dropped trailing-slash matching; serve /documents/X/ as /documents/X again. */
    @Bean
    public FilterRegistrationBean<UrlHandlerFilter> trailingSlash() {
        FilterRegistrationBean<UrlHandlerFilter> reg =
                new FilterRegistrationBean<>(UrlHandlerFilter.trailingSlashHandler("/**").wrapRequest().build());
        reg.setOrder(Ordered.HIGHEST_PRECEDENCE);
        return reg;
    }

    /** Tomcat drops the error dispatch for an oversize multipart body, so render the error here. */
    @ExceptionHandler(MaxUploadSizeExceededException.class)
    public ResponseEntity<Map<String, Object>> tooLarge(HttpServletRequest request, WebRequest webRequest) {
        request.setAttribute(RequestDispatcher.ERROR_STATUS_CODE, HttpServletResponse.SC_INTERNAL_SERVER_ERROR);
        request.setAttribute(RequestDispatcher.ERROR_REQUEST_URI, request.getRequestURI());
        Map<String, Object> body = errorAttributes.getErrorAttributes(webRequest, ErrorAttributeOptions.defaults());
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).contentType(MediaType.APPLICATION_JSON).body(body);
    }
}
