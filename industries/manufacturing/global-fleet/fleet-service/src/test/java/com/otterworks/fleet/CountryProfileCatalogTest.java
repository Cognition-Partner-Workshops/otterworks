package com.otterworks.fleet;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.dataformat.yaml.YAMLFactory;
import com.otterworks.fleet.config.CountryProfile;
import java.lang.reflect.RecordComponent;
import java.math.BigDecimal;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.Currency;
import java.util.Locale;
import java.util.Map;
import java.util.stream.Collectors;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.core.env.Environment;
import org.springframework.boot.test.context.SpringBootTest;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;

@SpringBootTest
class CountryProfileCatalogTest extends AbstractPostgresIntegrationTest {

    @Autowired
    private CountryProfile profile;

    @Autowired
    private Environment environment;

    @Test
    void GF01_countryParametersComeFromProfile() throws Exception {
        JsonNode catalog = new ObjectMapper().readTree(Path.of("../discovery/catalog.json").toFile());
        String activeProfile = Arrays.stream(environment.getActiveProfiles())
                .filter(name -> catalog.path("profiles").has(name))
                .findFirst()
                .orElseThrow(() -> new AssertionError("An active uk or de profile is required"));
        JsonNode expectedValues = catalog.path("profiles").path(activeProfile);
        Map<String, RecordComponent> components = Arrays.stream(CountryProfile.class.getRecordComponents())
                .collect(Collectors.toMap(RecordComponent::getName, component -> component));

        expectedValues.fields().forEachRemaining(entry -> {
            String componentName = toCamelCase(entry.getKey());
            RecordComponent component = components.get(componentName);
            assertNotNull(component, "CountryProfile is missing catalog key " + entry.getKey());
            try {
                Object actual = component.getAccessor().invoke(profile);
                assertCatalogValue(entry.getValue(), actual, entry.getKey());
            } catch (ReflectiveOperationException exception) {
                throw new AssertionError("Cannot read profile field " + componentName, exception);
            }
        });

        JsonNode baseConfiguration = new ObjectMapper(new YAMLFactory())
                .readTree(Files.readString(Path.of("src/main/resources/application.yml")));
        assertFalse(baseConfiguration.path("fleet").has("country"),
                "The base application.yml must not set fleet.country");
    }

    private static void assertCatalogValue(JsonNode expected, Object actual, String key) {
        assertNotNull(actual, "Bound value for " + key);
        if (actual instanceof BigDecimal decimal) {
            assertEquals(expected.asText(), decimal.toString(), key);
        } else if (actual instanceof Currency currency) {
            assertEquals(expected.asText(), currency.getCurrencyCode(), key);
        } else if (actual instanceof Enum<?> enumValue) {
            assertEquals(expected.asText().toUpperCase(Locale.ROOT), enumValue.name(), key);
        } else if (actual instanceof Integer integer) {
            assertEquals(expected.intValue(), integer, key);
        } else if (actual instanceof Boolean bool) {
            assertEquals(expected.booleanValue(), bool, key);
        } else {
            assertEquals(expected.asText(), actual, key);
        }
    }

    private static String toCamelCase(String snakeCase) {
        StringBuilder result = new StringBuilder();
        boolean capitalizeNext = false;
        for (char character : snakeCase.toCharArray()) {
            if (character == '_') {
                capitalizeNext = true;
            } else {
                result.append(capitalizeNext ? Character.toUpperCase(character) : character);
                capitalizeNext = false;
            }
        }
        return result.toString();
    }

}
