package com.otterworks.report.ubw;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * The thirty SSRS report datasets of the Usage &amp; Billing Warehouse, generated from
 * migration/snowflake/source/reports by migration/snowflake/consumers/report_catalog.py.
 * Each report carries the legacy SQL Server query and the Snowflake query against REPORTS.&lt;report&gt;.
 */
@Component
public class UbwReportCatalog {

    static final String RESOURCE = "/ubw/reports.json";

    private final Map<String, Report> reports;

    public UbwReportCatalog() {
        this(UbwReportCatalog.class.getResourceAsStream(RESOURCE));
    }

    UbwReportCatalog(InputStream stream) {
        if (stream == null) {
            throw new IllegalStateException("UBW report catalog " + RESOURCE + " is missing");
        }
        try (InputStream input = stream) {
            Catalog catalog = new ObjectMapper().readValue(input, Catalog.class);
            Map<String, Report> byName = new LinkedHashMap<String, Report>();
            for (Report report : catalog.reports) {
                byName.put(report.name, report);
            }
            this.reports = Collections.unmodifiableMap(byName);
        } catch (IOException e) {
            throw new UncheckedIOException("Cannot read UBW report catalog " + RESOURCE, e);
        }
    }

    public Collection<Report> all() {
        return reports.values();
    }

    public Optional<Report> find(String name) {
        return Optional.ofNullable(reports.get(name));
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class Catalog {
        public List<Report> reports = new ArrayList<Report>();
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class Report {
        public String name;
        public List<String> fields = new ArrayList<String>();
        public List<Parameter> parameters = new ArrayList<Parameter>();
        public Query sqlserver;
        public Query snowflake;

        public Query queryFor(UbwBackend backend) {
            return backend == UbwBackend.SNOWFLAKE ? snowflake : sqlserver;
        }

        public String defaultFor(String parameter) {
            for (Parameter candidate : parameters) {
                if (candidate.name.equals(parameter)) {
                    return candidate.defaultValue;
                }
            }
            return null;
        }
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class Parameter {
        public String name;
        @com.fasterxml.jackson.annotation.JsonProperty("default")
        public String defaultValue;
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class Query {
        public String source;
        public String query;
        public List<String> parameters = new ArrayList<String>();
    }
}
