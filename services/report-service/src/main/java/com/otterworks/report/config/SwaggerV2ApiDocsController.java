package com.otterworks.report.config;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.servlet.http.HttpServletRequest;
import org.springdoc.webmvc.api.OpenApiWebMvcResource;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.io.IOException;
import java.net.URI;
import java.util.Iterator;
import java.util.LinkedHashSet;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * Serves {@code /v2/api-docs}, the SpringFox URL, as a Swagger 2.0 document derived from the
 * springdoc OpenAPI 3 model, so existing Swagger 2 clients keep working.
 *
 * The conversion covers what this API uses: path/query parameters, JSON request bodies, response
 * schemas and component schemas ({@code #/components/schemas} becomes {@code #/definitions}).
 * Lives outside the scanned controller package, so it is not part of the document itself.
 */
@RestController
public class SwaggerV2ApiDocsController {

    static final String PATH = "/v2/api-docs";

    private static final String V3_REF = "#/components/schemas/";
    private static final String V2_REF = "#/definitions/";

    private final OpenApiWebMvcResource openApiResource;
    private final ObjectMapper mapper;

    public SwaggerV2ApiDocsController(OpenApiWebMvcResource openApiResource, ObjectMapper mapper) {
        this.openApiResource = openApiResource;
        this.mapper = mapper;
    }

    @GetMapping(value = PATH, produces = MediaType.APPLICATION_JSON_VALUE)
    public JsonNode apiDocs(HttpServletRequest request, Locale locale) throws IOException {
        JsonNode v3 = mapper.readTree(openApiResource.openapiJson(request, PATH, locale));
        return toSwagger2(v3);
    }

    ObjectNode toSwagger2(JsonNode v3) {
        ObjectNode v2 = mapper.createObjectNode();
        v2.put("swagger", "2.0");
        copy(v3, v2, "info");
        hostAndBasePath(v3, v2);
        copy(v3, v2, "tags");

        ObjectNode paths = v2.putObject("paths");
        Iterator<Map.Entry<String, JsonNode>> pathIt = v3.path("paths").fields();
        while (pathIt.hasNext()) {
            Map.Entry<String, JsonNode> path = pathIt.next();
            ObjectNode operations = paths.putObject(path.getKey());
            Iterator<Map.Entry<String, JsonNode>> opIt = path.getValue().fields();
            while (opIt.hasNext()) {
                Map.Entry<String, JsonNode> op = opIt.next();
                operations.set(op.getKey(), operation(op.getValue()));
            }
        }

        JsonNode schemas = v3.path("components").path("schemas");
        if (schemas.isObject()) {
            v2.set("definitions", rewriteRefs(schemas.deepCopy()));
        }
        return v2;
    }

    private void hostAndBasePath(JsonNode v3, ObjectNode v2) {
        JsonNode servers = v3.path("servers");
        String basePath = "/";
        if (servers.isArray() && servers.size() > 0) {
            URI server = URI.create(servers.get(0).path("url").asText("/"));
            if (server.getAuthority() != null) {
                v2.put("host", server.getAuthority());
            }
            if (server.getPath() != null && !server.getPath().isEmpty()) {
                basePath = server.getPath();
            }
        }
        v2.put("basePath", basePath);
    }

    private ObjectNode operation(JsonNode op) {
        ObjectNode out = mapper.createObjectNode();
        copy(op, out, "tags");
        copy(op, out, "summary");
        copy(op, out, "description");
        copy(op, out, "operationId");

        ArrayNode parameters = mapper.createArrayNode();
        for (JsonNode param : op.path("parameters")) {
            ObjectNode p = mapper.createObjectNode();
            copy(param, p, "name");
            copy(param, p, "in");
            copy(param, p, "description");
            p.put("required", param.path("required").asBoolean(false));
            JsonNode schema = param.path("schema");
            for (String key : new String[] {"type", "format", "items", "enum", "default"}) {
                copy(schema, p, key);
            }
            parameters.add(rewriteRefs(p));
        }

        JsonNode body = op.path("requestBody");
        if (body.isObject()) {
            out.set("consumes", mapper.valueToTree(body.path("content").properties().stream()
                    .map(Map.Entry::getKey).toList()));
            ObjectNode p = parameters.addObject();
            p.put("in", "body");
            p.put("name", "body");
            p.put("required", body.path("required").asBoolean(false));
            JsonNode schema = firstSchema(body.path("content"));
            if (schema != null) {
                p.set("schema", rewriteRefs(schema.deepCopy()));
            }
        }
        if (!parameters.isEmpty()) {
            out.set("parameters", parameters);
        }

        Set<String> produces = new LinkedHashSet<>();
        ObjectNode responses = out.putObject("responses");
        Iterator<Map.Entry<String, JsonNode>> it = op.path("responses").fields();
        while (it.hasNext()) {
            Map.Entry<String, JsonNode> response = it.next();
            ObjectNode r = responses.putObject(response.getKey());
            r.put("description", response.getValue().path("description").asText(""));
            JsonNode content = response.getValue().path("content");
            content.fieldNames().forEachRemaining(produces::add);
            JsonNode schema = firstSchema(content);
            if (schema != null) {
                r.set("schema", "binary".equals(schema.path("format").asText())
                        ? mapper.createObjectNode().put("type", "file")
                        : rewriteRefs(schema.deepCopy()));
            }
        }
        if (!produces.isEmpty()) {
            out.set("produces", mapper.valueToTree(produces));
        }
        copy(op, out, "deprecated");
        return out;
    }

    private static JsonNode firstSchema(JsonNode content) {
        Iterator<JsonNode> media = content.elements();
        return media.hasNext() && media.next().has("schema") ? content.elements().next().get("schema") : null;
    }

    private static JsonNode rewriteRefs(JsonNode node) {
        if (node.isObject()) {
            ObjectNode object = (ObjectNode) node;
            JsonNode ref = object.get("$ref");
            if (ref != null && ref.isTextual() && ref.asText().startsWith(V3_REF)) {
                object.put("$ref", V2_REF + ref.asText().substring(V3_REF.length()));
            }
            object.elements().forEachRemaining(SwaggerV2ApiDocsController::rewriteRefs);
        } else if (node.isArray()) {
            node.elements().forEachRemaining(SwaggerV2ApiDocsController::rewriteRefs);
        }
        return node;
    }

    private static void copy(JsonNode from, ObjectNode to, String field) {
        JsonNode value = from.get(field);
        if (value != null && !value.isMissingNode() && !value.isNull()) {
            to.set(field, value.deepCopy());
        }
    }
}
