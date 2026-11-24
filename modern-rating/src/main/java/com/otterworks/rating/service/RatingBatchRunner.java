package com.otterworks.rating.service;

import com.otterworks.rating.model.PolicyRecordReader;
import com.otterworks.rating.model.Quote;
import com.otterworks.rating.util.Sha256;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Component;

/** Batch mode: --rating.batch.input=policies.dat --rating.batch.output=rated.txt */
@Component
@ConditionalOnProperty(prefix = "rating.batch", name = "input")
public class RatingBatchRunner implements ApplicationRunner {

    private static final Logger log = LoggerFactory.getLogger(RatingBatchRunner.class);

    private final RatingService rating;
    private final Environment env;

    public RatingBatchRunner(RatingService rating, Environment env) {
        this.rating = rating;
        this.env = env;
    }

    @Override
    public void run(ApplicationArguments args) throws Exception {
        Path input = Path.of(env.getRequiredProperty("rating.batch.input"));
        Path output = Path.of(env.getRequiredProperty("rating.batch.output"));
        List<Quote> quotes = Files.readAllLines(input).stream()
                .filter(l -> !l.isBlank())
                .map(PolicyRecordReader::read)
                .map(rating::rate)
                .toList();
        if (output.getParent() != null) {
            Files.createDirectories(output.getParent());
        }
        Files.write(output, quotes.stream().map(Quote::asLine).toList());
        Map<String, Long> counts = quotes.stream()
                .collect(Collectors.groupingBy(Quote::status, Collectors.counting()));
        log.info("MODERN RUN={}", Sha256.hex(String.join("\n", quotes.stream().map(Quote::asLine).toList())));
        log.info("MODERN READ={} OK={} DEC={} REJ={}", quotes.size(), counts.getOrDefault("OK", 0L),
                counts.getOrDefault("DEC", 0L), counts.getOrDefault("REJ", 0L));
    }
}
