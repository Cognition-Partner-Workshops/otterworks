package com.otterworks.rating;

import static org.assertj.core.api.Assertions.assertThat;

import com.otterworks.rating.config.RatingProperties;
import com.otterworks.rating.service.RatingBatchRunner;
import com.otterworks.rating.service.RatingService;
import com.otterworks.rating.service.RatingTables;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.boot.DefaultApplicationArguments;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;
import org.springframework.mock.env.MockEnvironment;

@ExtendWith(OutputCaptureExtension.class)
class RatingBatchRunnerTest {

    @Test
    void logsTheFullSha256OfTheCanonicalQuoteLines(@TempDir Path directory, CapturedOutput logs) throws Exception {
        Path input = directory.resolve("policies.dat");
        Path output = directory.resolve("rated.txt");
        Files.write(input, List.of("P0000009GLIL9134000020260315000000000050100500N00{00NNN",
                "P0000010GLIL9134000020260315000000000050100500N00{00NNN"));

        RatingProperties props = new RatingProperties("../legacy-rating/tables", null);
        RatingService rating = new RatingService(new RatingTables(props), props);
        MockEnvironment env = new MockEnvironment()
                .withProperty("rating.batch.input", input.toString())
                .withProperty("rating.batch.output", output.toString());

        new RatingBatchRunner(rating, env).run(new DefaultApplicationArguments());

        assertThat(Files.readAllLines(output)).containsExactly(
                "P0000009|REJ|EX|0|0|N|0|0|0|", "P0000010|REJ|EX|0|0|N|0|0|0|");
        assertThat(logs).contains("MODERN RUN=C5472B8358017BDCB9C664CD733FA06C7EF6D53430F8C61E4815DF1501620414");
    }
}
