package com.otterworks.report.ubw;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * The Usage &amp; Billing Warehouse reports (the thirty SSRS datasets) for report-service and the
 * admin-dashboard usage pages. UBW_BACKEND=sqlserver reads mart/fact on SQL Server with the RDL
 * query; UBW_BACKEND=snowflake reads the REPORTS views of the run's Snowflake database.
 */
@RestController
@RequestMapping("/api/v1/reports/ubw")
public class UbwReportController {

    private final UbwReportCatalog catalog;
    private final UbwReportRepository repository;

    public UbwReportController(UbwReportCatalog catalog, UbwReportRepository repository) {
        this.catalog = catalog;
        this.repository = repository;
    }

    @GetMapping
    public Map<String, Object> list() {
        List<Map<String, Object>> reports = new ArrayList<Map<String, Object>>();
        for (UbwReportCatalog.Report report : catalog.all()) {
            Map<String, Object> entry = new LinkedHashMap<String, Object>();
            entry.put("name", report.name);
            entry.put("source", report.queryFor(repository.backend()).source);
            entry.put("fields", report.fields);
            reports.add(entry);
        }
        Map<String, Object> body = new LinkedHashMap<String, Object>();
        body.put("backend", repository.backend().label());
        body.put("reports", reports);
        return body;
    }

    @GetMapping("/{report}")
    public ResponseEntity<Map<String, Object>> report(@PathVariable("report") String name,
                                                      @RequestParam Map<String, String> request) {
        Optional<UbwReportCatalog.Report> found = catalog.find(name);
        if (!found.isPresent()) {
            return error(HttpStatus.NOT_FOUND, "Unknown UBW report " + name);
        }
        UbwReportCatalog.Report report = found.get();
        Map<String, String> parameters = new LinkedHashMap<String, String>();
        for (UbwReportCatalog.Parameter parameter : report.parameters) {
            String value = request.containsKey(parameter.name) ? request.get(parameter.name)
                    : request.getOrDefault(lowerFirst(parameter.name), parameter.defaultValue);
            parameters.put(parameter.name, value);
        }
        try {
            LocalDate.parse(parameters.get("BusinessDate"));
        } catch (DateTimeParseException | NullPointerException e) {
            return error(HttpStatus.BAD_REQUEST, "businessDate must be yyyy-MM-dd");
        }
        List<Map<String, Object>> rows = repository.run(report, parameters);
        Map<String, Object> body = new LinkedHashMap<String, Object>();
        body.put("report", report.name);
        body.put("backend", repository.backend().label());
        body.put("source", report.queryFor(repository.backend()).source);
        body.put("parameters", parameters);
        body.put("fields", report.fields);
        body.put("rowCount", rows.size());
        body.put("rows", rows);
        return ResponseEntity.ok(body);
    }

    private static String lowerFirst(String value) {
        return Character.toLowerCase(value.charAt(0)) + value.substring(1);
    }

    private static ResponseEntity<Map<String, Object>> error(HttpStatus status, String message) {
        Map<String, Object> body = new LinkedHashMap<String, Object>();
        body.put("error", message);
        return ResponseEntity.status(status).body(body);
    }
}
