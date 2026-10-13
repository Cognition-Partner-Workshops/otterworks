package com.otterworks.report.ubw;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/** Runs a UBW report's dataset query on the backend UBW_BACKEND selects. */
@Repository
public class UbwReportRepository {

    private final UbwDataSources dataSources;

    public UbwReportRepository(UbwDataSources dataSources) {
        this.dataSources = dataSources;
    }

    public UbwBackend backend() {
        return dataSources.backend();
    }

    public List<Map<String, Object>> run(UbwReportCatalog.Report report, Map<String, String> parameters) {
        UbwReportCatalog.Query query = report.queryFor(backend());
        List<Object> arguments = new ArrayList<Object>();
        for (String name : query.parameters) {
            String value = parameters.get(name);
            arguments.add("BusinessDate".equals(name) ? java.sql.Date.valueOf(LocalDate.parse(value)) : value);
        }
        JdbcTemplate jdbc = new JdbcTemplate(dataSources.dataSource());
        List<Map<String, Object>> rows = jdbc.queryForList(query.query, arguments.toArray());
        List<Map<String, Object>> normalised = new ArrayList<Map<String, Object>>(rows.size());
        for (Map<String, Object> row : rows) {
            Map<String, Object> copy = new LinkedHashMap<String, Object>();
            for (Map.Entry<String, Object> entry : row.entrySet()) {
                copy.put(entry.getKey().toLowerCase(Locale.ROOT), entry.getValue());
            }
            normalised.add(copy);
        }
        return normalised;
    }
}
