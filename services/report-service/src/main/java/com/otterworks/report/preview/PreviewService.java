package com.otterworks.report.preview;

import com.otterworks.report.service.ReportHeaderRenderer;
import org.springframework.stereotype.Service;

/**
 * Renders configured template bodies using report metadata interpolation.
 */
@Service
public class PreviewService {

    private final PreviewTemplates templates;
    private final ReportHeaderRenderer renderer;

    public PreviewService(PreviewTemplates templates, ReportHeaderRenderer renderer) {
        this.templates = templates;
        this.renderer = renderer;
    }

    public String render(String templateId) {
        String body = templates.body(templateId);
        if (body == null) {
            throw new PreviewDeniedException();
        }
        return renderer.resolveConfigured(body);
    }
}
