package com.otterworks.ottershops.pricing;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.io.InputStream;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.io.ResourceLoader;

@Configuration
public class PromotionConfig {
    private static final Logger log = LoggerFactory.getLogger(PromotionConfig.class);

    @Bean
    public Promotion promotion(
            ResourceLoader loader,
            ObjectMapper mapper,
            @Value("${ottershops.promotions.file}") String file,
            @Value("${ottershops.promotions.enabled-override:}") String enabledOverride) throws IOException {
        Promotion promo;
        try (InputStream in = loader.getResource(file).getInputStream()) {
            promo = mapper.readValue(in, Promotion.class);
        }
        if (enabledOverride != null && !enabledOverride.isBlank()) {
            promo = promo.withEnabled(Boolean.parseBoolean(enabledOverride.trim()));
        }
        log.info("promotion {} loaded from {} (enabled={}, {} -> {})", promo.id(), file, promo.enabled(), promo.startsAt(), promo.endsAt());
        return promo;
    }
}
