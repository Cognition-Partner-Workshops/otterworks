package com.halvergate.accountevents.runtime;

import java.io.IOException;
import java.util.Objects;
import org.springframework.beans.factory.config.YamlPropertiesFactoryBean;
import org.springframework.core.env.PropertiesPropertySource;
import org.springframework.core.env.PropertySource;
import org.springframework.core.io.support.EncodedResource;
import org.springframework.core.io.support.PropertySourceFactory;

public class PackageYamlFactory implements PropertySourceFactory {
    @Override
    public PropertySource<?> createPropertySource(String name, EncodedResource resource) throws IOException {
        YamlPropertiesFactoryBean yaml = new YamlPropertiesFactoryBean();
        yaml.setResources(resource.getResource());
        return new PropertiesPropertySource(resource.getResource().getDescription(),
            Objects.requireNonNull(yaml.getObject()));
    }
}
