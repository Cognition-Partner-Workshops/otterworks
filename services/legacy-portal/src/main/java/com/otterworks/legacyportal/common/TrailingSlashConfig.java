package com.otterworks.legacyportal.common;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.filter.UrlHandlerFilter;

/** Spring Framework 6+ no longer matches a trailing slash; keep the Boot 2 routes ("/api/x/" == "/api/x"). */
@Configuration
public class TrailingSlashConfig {

    @Bean
    public UrlHandlerFilter trailingSlashFilter() {
        return UrlHandlerFilter.trailingSlashHandler("/**").wrapRequest().build();
    }
}
