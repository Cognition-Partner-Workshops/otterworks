package com.otterworks.rating;

import static org.assertj.core.api.Assertions.assertThat;

import com.otterworks.rating.controller.AdminController;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.Test;

class AdminControllerRestoreTest {

    @Test
    void doesNotReferenceNativeObjectDeserialization() throws IOException {
        try (var classFile = AdminController.class.getResourceAsStream("AdminController.class")) {
            assertThat(classFile).isNotNull();
            assertThat(new String(classFile.readAllBytes(), StandardCharsets.ISO_8859_1))
                    .doesNotContain("java/io/ObjectInputStream");
        }
    }
}
