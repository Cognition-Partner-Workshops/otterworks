package com.otterworks.fleet;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertTrue;

class CountryConditionalTest {

    private static final Pattern IF_CONDITION =
            Pattern.compile("(?is)\\b(?:if|else\\s+if)\\s*\\(([^)]*)\\)");
    private static final Pattern TERNARY_CONDITION =
            Pattern.compile("(?s)([^?;{}\\n]+)\\?");
    private static final Pattern COUNTRY_TOKEN = Pattern.compile(
            "(?i)(?:\"(?:uk|de|gb)\"|'(?:uk|de|gb)'|\\b(?:UK|DE|GB|GERMANY|BRITAIN|ENGLAND)\\b)");

    @Test
    void GF01_noCountryNameInConditionals() throws IOException {
        Path sourceRoot = Path.of("src/main/java");
        List<String> violations = new ArrayList<>();
        try (Stream<Path> sources = Files.walk(sourceRoot)) {
            sources.filter(path -> path.toString().endsWith(".java")).forEach(path -> {
                try {
                    String source = Files.readString(path);
                    findMatches(path, source, IF_CONDITION, violations);
                    findMatches(path, source, TERNARY_CONDITION, violations);
                } catch (IOException exception) {
                    throw new IllegalStateException(exception);
                }
            });
        }
        assertTrue(violations.isEmpty(), () -> "Country names in conditionals:\n" + String.join("\n", violations));
    }

    private static void findMatches(Path path, String source, Pattern pattern, List<String> violations) {
        Matcher matcher = pattern.matcher(source);
        while (matcher.find()) {
            String condition = matcher.group(1);
            if (COUNTRY_TOKEN.matcher(condition).find()) {
                int line = (int) source.substring(0, matcher.start()).chars().filter(c -> c == '\n').count() + 1;
                violations.add(path + ":" + line + " " + condition.strip());
            }
        }
    }
}
