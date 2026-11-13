package com.otterworks.report.preview;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

import javax.servlet.http.HttpServletRequest;
import java.security.Principal;

/**
 * Text previews available only when template preview is enabled.
 */
@RestController
@ConditionalOnProperty(prefix = "report.template-preview", name = "enabled", havingValue = "true")
public class PreviewController {

    private final PreviewAuthorizer authorizer;
    private final PreviewService service;

    public PreviewController(PreviewAuthorizer authorizer, PreviewService service) {
        this.authorizer = authorizer;
        this.service = service;
    }

    @GetMapping(value = "/api/v1/reports/templates/{templateId}/preview", produces = MediaType.TEXT_PLAIN_VALUE)
    public String preview(@PathVariable("templateId") String templateId,
                          Principal principal, HttpServletRequest request) {
        authorizer.authorize(templateId, principal, request);
        return service.render(templateId);
    }
}
