package com.otterworks.insurance.claimshub.triage;

import java.io.IOException;
import java.io.InputStreamReader;
import java.io.Reader;
import java.io.StringReader;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import org.apache.commons.csv.CSVFormat;
import org.apache.commons.csv.CSVRecord;
import org.springframework.core.io.Resource;

/**
 * The ClaimTriage policy as data: one CSV row per rule with name, priority, condition, outcome
 * and reason. Rules are held in agenda order: descending priority, file order within a priority.
 */
public final class RulesTable {

    static final String[] HEADER = {"name", "priority", "condition", "outcome", "reason"};

    private final List<TriageRule> rules;

    private RulesTable(List<TriageRule> rules) {
        this.rules = List.copyOf(rules);
    }

    public static RulesTable load(Resource resource) {
        try (Reader reader = new InputStreamReader(resource.getInputStream(), StandardCharsets.UTF_8)) {
            return load(reader);
        } catch (IOException e) {
            throw new UncheckedIOException("cannot read rules table " + resource, e);
        }
    }

    public static RulesTable parse(String csv) {
        return load(new StringReader(csv));
    }

    public static RulesTable load(Reader reader) {
        CSVFormat format = CSVFormat.RFC4180.builder()
                .setHeader(HEADER)
                .setSkipHeaderRecord(true)
                .setIgnoreSurroundingSpaces(true)
                .setIgnoreEmptyLines(true)
                .build();
        List<TriageRule> rules = new ArrayList<>();
        Set<String> names = new HashSet<>();
        try {
            for (CSVRecord row : format.parse(reader)) {
                if (row.size() != HEADER.length) {
                    throw new IllegalArgumentException("line " + row.getRecordNumber() + ": expected "
                            + HEADER.length + " columns, found " + row.size());
                }
                String name = row.get("name");
                if (!names.add(name)) {
                    throw new IllegalArgumentException("duplicate rule " + name);
                }
                rules.add(new TriageRule(name, Integer.parseInt(row.get("priority")),
                        Condition.parse(row.get("condition")), row.get("outcome"), row.get("reason")));
            }
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
        if (rules.isEmpty()) {
            throw new IllegalArgumentException("rules table has no rules");
        }
        rules.sort(Comparator.comparingInt(TriageRule::priority).reversed());
        return new RulesTable(rules);
    }

    public List<TriageRule> rules() {
        return rules;
    }

    public List<String> names() {
        return rules.stream().map(TriageRule::name).toList();
    }
}
