package com.bank.kyc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest
@AutoConfigureMockMvc
class DocumentControllerTest {

    @TempDir
    static Path uploads;

    @DynamicPropertySource
    static void props(DynamicPropertyRegistry r) {
        r.add("kyc.upload-dir", uploads::toString);
    }

    @Autowired
    MockMvc mvc;

    @Test
    void healthIsUpWhenUploadDirIsWritable() throws Exception {
        mvc.perform(get("/health")).andExpect(status().isOk()).andExpect(jsonPath("$.status").value("UP"));
    }

    @Test
    void uploadThenList() throws Exception {
        MockMultipartFile f = new MockMultipartFile("file", "scan.png", "image/png", new byte[7]);
        mvc.perform(multipart("/documents/HG611000002").file(f).param("kind", "passport"))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.bytes").value(7))
                .andExpect(jsonPath("$.kind").value("passport"));
        mvc.perform(get("/documents/HG611000002")).andExpect(status().isOk()).andExpect(jsonPath("$.length()").value(1));
    }

    @Test
    void badCustomerIsRejected() throws Exception {
        mvc.perform(get("/documents/abc")).andExpect(status().isBadRequest());
    }
}
