package com.otterworks.report.preview;

import com.otterworks.report.service.ReportHeaderRenderer;
import org.junit.Test;

import java.util.Properties;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertThrows;

public class PreviewServiceTest {

    @Test
    public void rendersEmptyBody() {
        Properties properties = new Properties();
        properties.setProperty("preview.body.empty", "");
        PreviewService service = new PreviewService(new PreviewTemplates(properties), new ReportHeaderRenderer());
        assertEquals("", service.render("empty"));
    }

    @Test
    public void deniesMissingBody() {
        PreviewService service = new PreviewService(new PreviewTemplates(new Properties()), new ReportHeaderRenderer());
        assertThrows(PreviewDeniedException.class, () -> service.render("unknown"));
    }
}
