package com.otterworks.rating.controller;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class AdminTableBoundaryTest {

    private static final Path ROOT = Path.of("/srv").toAbsolutePath();
    private static final Path TABLES = ROOT.resolve("tables");

    @Test
    void acceptsAFileUnderTheTablesDirectory() {
        assertThat(AdminController.withinTablesDir(TABLES, TABLES.resolve("rates.csv"))).isTrue();
    }

    @ParameterizedTest
    @ValueSource(strings = {"other", "tables2"})
    void rejectsAFileInASiblingDirectory(String directory) {
        assertThat(AdminController.withinTablesDir(TABLES, ROOT.resolve(directory).resolve("rates.csv"))).isFalse();
    }
}
