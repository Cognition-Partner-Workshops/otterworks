package com.otterworks.rating;

import static org.assertj.core.api.Assertions.assertThat;

import com.otterworks.rating.controller.AdminController;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.regex.Pattern;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

class AdminTableNameTest {

    @Test
    void allowsEveryShippedTableFilename() throws Exception {
        Pattern allowedName = (Pattern) ReflectionTestUtils.getField(AdminController.class, "TABLE_NAME");
        try (var tables = Files.list(Path.of("../legacy-rating/tables"))) {
            var filenames = tables.filter(Files::isRegularFile).map(path -> path.getFileName().toString()).toList();
            assertThat(filenames).isNotEmpty().allMatch(name -> allowedName.matcher(name).matches());
        }
    }
}
