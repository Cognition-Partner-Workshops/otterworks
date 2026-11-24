package com.otterworks.rating.service;

import com.otterworks.rating.config.RatingProperties;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.math.BigDecimal;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Optional;
import org.springframework.stereotype.Component;

/** The shared flat-file rating tables, kept in file order. */
@Component
public class RatingTables {

    public record DatedRange(LocalDate from, LocalDate to) {
        boolean covers(LocalDate date) {
            return !date.isBefore(from) && (to == null || !date.isAfter(to));
        }
    }

    public record ClassRate(String line, String classCode, BigDecimal rate, DatedRange range) {}

    public record TerritoryFactor(String line, String territory, BigDecimal factor, DatedRange range) {}

    public record Eligibility(String line, String classCode, String state, boolean eligible, String reason) {}

    public record Minimum(String line, String state, BigDecimal minimum) {}

    public record Override(String line, String classCode, String territory, BigDecimal factor, DatedRange range) {}

    public static final String ALL_STATES = "**";
    public static final String DEFAULT_TERRITORY = "000";

    private final List<ClassRate> classRates;
    private final List<TerritoryFactor> territoryFactors;
    private final List<Eligibility> eligibility;
    private final List<Minimum> minimums;
    private final List<Override> overrides;

    public RatingTables(RatingProperties properties) {
        Path dir = Path.of(properties.tablesDir());
        classRates = rows(dir.resolve("class-factors.dat")).stream()
                .map(f -> new ClassRate(f[0], f[1], new BigDecimal(f[2]), range(f, 3))).toList();
        territoryFactors = rows(dir.resolve("territory-factors.dat")).stream()
                .map(f -> new TerritoryFactor(f[0], f[1], new BigDecimal(f[2]), range(f, 3))).toList();
        eligibility = rows(dir.resolve("line-eligibility.dat")).stream()
                .map(f -> new Eligibility(f[0], f[1], f[2], "Y".equals(f[3]), f.length > 4 ? f[4] : "")).toList();
        minimums = rows(dir.resolve("minimum-premium.dat")).stream()
                .map(f -> new Minimum(f[0], f[1], new BigDecimal(f[2]))).toList();
        overrides = rows(dir.resolve("overrides.dat")).stream()
                .map(f -> new Override(f[0], f[1], f[2], new BigDecimal(f[3]), range(f, 4))).toList();
    }

    public Optional<ClassRate> classRate(String line, String classCode, LocalDate on) {
        return classRates.stream()
                .filter(r -> r.line().equals(line) && r.classCode().equals(classCode) && r.range().covers(on))
                .findFirst();
    }

    public Optional<TerritoryFactor> territory(String line, String territory, LocalDate on) {
        return territoryFactors.stream()
                .filter(r -> r.line().equals(line) && r.territory().equals(territory) && r.range().covers(on))
                .findFirst();
    }

    public Optional<TerritoryFactor> surcharge(String line, String code) {
        return territoryFactors.stream()
                .filter(r -> r.line().equals(line) && r.territory().equals(code))
                .reduce((first, second) -> second);
    }

    public Optional<Eligibility> eligibility(String line, String classCode, String state) {
        List<Eligibility> forClass = eligibility.stream()
                .filter(r -> r.line().equals(line) && r.classCode().equals(classCode)).toList();
        return forClass.stream().filter(r -> r.state().equals(state)).findFirst()
                .or(() -> forClass.stream().filter(r -> r.state().equals(ALL_STATES)).findFirst());
    }

    public Optional<Minimum> minimum(String line, String state) {
        List<Minimum> forLine = minimums.stream().filter(r -> r.line().equals(line)).toList();
        return forLine.stream().filter(r -> r.state().equals(state)).findFirst()
                .or(() -> forLine.stream().filter(r -> r.state().equals(ALL_STATES)).findFirst());
    }

    public Optional<Override> override(String line, String classCode, String territory, LocalDate on) {
        return overrides.stream()
                .filter(r -> r.line().equals(line) && r.classCode().equals(classCode)
                        && r.territory().equals(territory) && r.range().covers(on))
                .findFirst();
    }

    private static DatedRange range(String[] fields, int fromIndex) {
        LocalDate from = date(fields[fromIndex]);
        LocalDate to = fields.length > fromIndex + 1 && !fields[fromIndex + 1].isBlank()
                ? date(fields[fromIndex + 1]) : null;
        return new DatedRange(from, to);
    }

    private static LocalDate date(String yyyymmdd) {
        return LocalDate.parse(yyyymmdd, DateTimeFormatter.BASIC_ISO_DATE);
    }

    private static List<String[]> rows(Path file) {
        try {
            return Files.readAllLines(file).stream()
                    .filter(l -> !l.isBlank() && !l.startsWith("*"))
                    .map(l -> java.util.Arrays.stream(l.split("\\|", -1)).map(String::trim).toArray(String[]::new))
                    .toList();
        } catch (IOException e) {
            throw new UncheckedIOException("cannot read rating table " + file, e);
        }
    }
}
