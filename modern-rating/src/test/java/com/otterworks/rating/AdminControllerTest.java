package com.otterworks.rating;

import static org.assertj.core.api.Assertions.assertThat;

import com.otterworks.rating.config.RatingProperties;
import com.otterworks.rating.controller.AdminController;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.http.HttpStatus;

class AdminControllerTest {

    private static final String KEY = "insrules-support";

    @TempDir
    Path root;

    private AdminController controller(Path tables) {
        return new AdminController(new RatingProperties(tables.toString(), null), null);
    }

    @Test
    void servesATableFromTheTablesDirectory() throws Exception {
        Path tables = Files.createDirectory(root.resolve("tables"));
        Files.writeString(tables.resolve("class-factors.dat"), "GL|91340|1.25");

        var response = controller(tables).table("class-factors.dat", KEY);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).isEqualTo("GL|91340|1.25");
    }

    @Test
    void refusesNamesThatLeaveTheTablesDirectory() throws Exception {
        Path tables = Files.createDirectory(root.resolve("tables"));
        Files.writeString(root.resolve("outside.txt"), "not a table");
        AdminController admin = controller(tables);

        assertThat(admin.table("../outside.txt", KEY).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(admin.table(root.resolve("outside.txt").toString(), KEY).getStatusCode())
                .isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(admin.table("..", KEY).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(admin.table(".", KEY).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
    }

    @Test
    void refusesALinkOutOfTheTablesDirectory() throws Exception {
        Path tables = Files.createDirectory(root.resolve("tables"));
        Path outside = Files.writeString(root.resolve("outside.txt"), "not a table");
        Files.createSymbolicLink(tables.resolve("linked.dat"), outside);

        assertThat(controller(tables).table("linked.dat", KEY).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
    }
}
