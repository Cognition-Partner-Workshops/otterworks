package com.otterworks.report.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Contact;
import io.swagger.v3.oas.models.info.Info;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * OpenAPI configuration using springdoc-openapi 2.x (replaces SpringFox, which does not run on Spring Boot 3).
 *
 * OpenAPI 3 is served at /v3/api-docs (as SpringFox 3 did) and limited to the controller package, as the
 * SpringFox Docket was (springdoc.packages-to-scan). The Swagger 2.0 document at /v2/api-docs is gone.
 */
@Configuration
public class SwaggerConfig {

    @Bean
    public OpenAPI apiInfo() {
        return new OpenAPI().info(new Info()
                .title("OtterWorks Report Service API")
                .description("Legacy report generation service for PDF, CSV, and Excel exports")
                .version("0.1.0")
                .contact(new Contact().name("OtterWorks Engineering").email("engineering@otterworks.example.com")));
    }
}
