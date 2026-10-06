package com.otterworks.legacyportal.lambda.common;

import org.apache.commons.configuration2.Configuration;
import org.apache.commons.configuration2.PropertiesConfiguration;
import org.apache.commons.configuration2.builder.FileBasedConfigurationBuilder;
import org.apache.commons.configuration2.builder.fluent.Parameters;
import org.apache.commons.configuration2.ex.ConfigurationException;

/**
 * Portal branding strings, loaded from {@code portal-settings.properties} with Commons
 * Configuration, mirroring the monolith's component.
 */
public class PortalBrandingSettings {

    private static final String SETTINGS_FILE = "portal-settings.properties";

    private final Configuration configuration;

    public PortalBrandingSettings() {
        try {
            FileBasedConfigurationBuilder<PropertiesConfiguration> builder =
                    new FileBasedConfigurationBuilder<>(PropertiesConfiguration.class)
                            .configure(
                                    new Parameters()
                                            .properties()
                                            .setFileName(SETTINGS_FILE)
                                            .setThrowExceptionOnMissing(false));
            this.configuration = builder.getConfiguration();
        } catch (ConfigurationException e) {
            throw new IllegalStateException("cannot load " + SETTINGS_FILE, e);
        }
    }

    public String bannerText() {
        return configuration.getString("portal.banner", "OtterWorks Portal");
    }

    public String supportContact() {
        return configuration.getString("portal.support", "");
    }

    public String interpolate(String template) {
        return String.valueOf(configuration.getInterpolator().interpolate(template));
    }
}
