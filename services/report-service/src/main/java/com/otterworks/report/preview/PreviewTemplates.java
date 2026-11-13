package com.otterworks.report.preview;

import org.springframework.stereotype.Component;

import java.io.IOException;
import java.io.InputStream;
import java.util.Properties;

/**
 * Template bodies and ownership directives read independently of Spring placeholders.
 */
@Component
public class PreviewTemplates {

    private final Properties templates;

    public PreviewTemplates() {
        this(loadTemplates());
    }

    public PreviewTemplates(Properties templates) {
        this.templates = templates;
    }

    private static Properties loadTemplates() {
        Properties properties = new Properties();
        try (InputStream in = PreviewTemplates.class.getClassLoader()
                .getResourceAsStream("report-template-preview.properties")) {
            if (in != null) {
                properties.load(in);
            }
        } catch (IOException e) {
            throw new IllegalStateException("Could not read preview templates", e);
        }
        return properties;
    }

    public String ownerDirective(String templateId) {
        return templates.getProperty("preview.owner." + templateId);
    }

    public String body(String templateId) {
        return templates.getProperty("preview.body." + templateId);
    }
}
