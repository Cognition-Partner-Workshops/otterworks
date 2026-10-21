package com.otterworks.auth.config;

import com.fasterxml.jackson.annotation.JsonPropertyOrder;
import org.springframework.boot.autoconfigure.jackson.Jackson2ObjectMapperBuilderCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.domain.PageImpl;

@Configuration
public class JacksonConfig {

  // Keeps the Page JSON field order that Spring Boot 3.2 / Spring Data 3.2 emitted.
  @JsonPropertyOrder({
    "content",
    "pageable",
    "last",
    "totalPages",
    "totalElements",
    "first",
    "size",
    "number",
    "sort",
    "numberOfElements",
    "empty"
  })
  abstract static class PageImplPropertyOrder {}

  @Bean
  public Jackson2ObjectMapperBuilderCustomizer pagePropertyOrderCustomizer() {
    return builder -> builder.mixIn(PageImpl.class, PageImplPropertyOrder.class);
  }
}
