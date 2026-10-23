package com.otterworks.report.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Contact;
import io.swagger.v3.oas.models.info.Info;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * springdoc-openapi configuration (replaces the SpringFox Docket).
 *
 * The OpenAPI 3 document is served at {@code /v3/api-docs}; {@link SwaggerV2ApiDocsController} keeps
 * the SpringFox Swagger 2 URL {@code /v2/api-docs} answering from the same model.
 */
@Configuration
public class OpenApiConfig {

    @Bean
    public OpenAPI reportServiceOpenApi() {
        return new OpenAPI().info(new Info()
                .title("OtterWorks Report Service API")
                .description("Legacy report generation service for PDF, CSV, and Excel exports")
                .version("0.1.0")
                .contact(new Contact().name("OtterWorks Engineering").email("engineering@otterworks.example.com")));
    }
}
