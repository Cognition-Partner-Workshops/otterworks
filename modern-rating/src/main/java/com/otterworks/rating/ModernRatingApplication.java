package com.otterworks.rating;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

@SpringBootApplication
@ConfigurationPropertiesScan
public class ModernRatingApplication {

    public static void main(String[] args) {
        SpringApplication.run(ModernRatingApplication.class, args);
    }
}
