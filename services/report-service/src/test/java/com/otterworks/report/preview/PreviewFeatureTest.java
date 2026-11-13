package com.otterworks.report.preview;

import com.otterworks.report.service.ReportHeaderRenderer;
import org.junit.Test;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;

import static org.junit.Assert.assertEquals;

public class PreviewFeatureTest {

    private final ApplicationContextRunner context = new ApplicationContextRunner()
            .withUserConfiguration(PreviewController.class, PreviewAuthorizer.class,
                    PreviewService.class, PreviewTemplates.class, ReportHeaderRenderer.class);

    @Test
    public void controllerIsAbsentByDefault() {
        context.run(application -> assertEquals(0, application.getBeansOfType(PreviewController.class).size()));
    }

    @Test
    public void controllerIsAbsentWhenDisabled() {
        context.withPropertyValues("report.template-preview.enabled=false")
                .run(application -> assertEquals(0, application.getBeansOfType(PreviewController.class).size()));
    }

    @Test
    public void controllerIsRegisteredWhenEnabled() {
        context.withPropertyValues("report.template-preview.enabled=true")
                .run(application -> assertEquals(1, application.getBeansOfType(PreviewController.class).size()));
    }
}
