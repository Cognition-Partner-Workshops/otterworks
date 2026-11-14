package com.otterworks.legacyportal.common;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.PathMatchConfigurer;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * Spring Framework 6 stopped matching "/path/" to "/path" by default. Clients of the portal
 * rely on the Boot 2.7 behavior (e.g. GET /api/announcements/), so it is kept on explicitly.
 */
@Configuration
public class TrailingSlashConfig implements WebMvcConfigurer {

    @Override
    @SuppressWarnings("deprecation")
    public void configurePathMatch(PathMatchConfigurer configurer) {
        configurer.setUseTrailingSlashMatch(true);
    }
}
