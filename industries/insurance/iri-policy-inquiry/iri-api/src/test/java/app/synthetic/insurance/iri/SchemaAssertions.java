package app.synthetic.insurance.iri;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.fasterxml.jackson.dataformat.yaml.YAMLFactory;
import com.networknt.schema.JsonSchemaFactory;
import com.networknt.schema.SchemaValidatorsConfig;
import com.networknt.schema.SpecVersion;
import java.io.IOException;
import java.nio.file.Path;
import static org.junit.jupiter.api.Assertions.assertTrue;

public final class SchemaAssertions {
    private SchemaAssertions() {}

    public static void assertValid(String component, String body) throws IOException {
        ObjectMapper yaml = new ObjectMapper(new YAMLFactory());
        JsonNode spec = yaml.readTree(Path.of("../vendor/iri-policy-inquiry-v1.1.5/PolicyInquiry_v1.1.5.yml").toFile());
        if (!spec.path("components").path("schemas").has(component)) {
            throw new IllegalArgumentException("Unknown component: " + component);
        }
        ObjectMapper json = new ObjectMapper();
        ObjectNode root = json.createObjectNode();
        root.put("$schema", "https://json-schema.org/draft/2020-12/schema");
        root.put("$ref", "#/components/schemas/" + component);
        root.set("components", spec.get("components"));
        SchemaValidatorsConfig config = new SchemaValidatorsConfig();
        config.setTypeLoose(false);
        var schema = JsonSchemaFactory.getInstance(SpecVersion.VersionFlag.V202012).getSchema(root, config);
        var errors = schema.validate(json.readTree(body));
        assertTrue(errors.isEmpty(), () -> errors.toString());
    }
}
