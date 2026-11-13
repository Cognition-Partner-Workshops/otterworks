package com.otterworks.report.preview;

import org.apache.commons.text.StringSubstitutor;
import org.springframework.stereotype.Component;

import javax.servlet.http.HttpServletRequest;
import java.security.Principal;

/**
 * Authorizes template owners and report administrators.
 * Missing, blank or unresolved ownership directives fail closed.
 */
@Component
public class PreviewAuthorizer {

    private final PreviewTemplates templates;

    public PreviewAuthorizer(PreviewTemplates templates) {
        this.templates = templates;
    }

    public void authorize(String templateId, Principal principal, HttpServletRequest request) {
        if (principal == null) {
            throw new PreviewDeniedException();
        }
        String owner = resolveOwner(templateId);
        if (!owner.equals(principal.getName()) && !request.isUserInRole("REPORT_ADMIN")) {
            throw new PreviewDeniedException();
        }
    }

    public String resolveOwner(String templateId) {
        String directive = templates.ownerDirective(templateId);
        if (directive == null) {
            throw new PreviewDeniedException();
        }
        try {
            StringSubstitutor substitutor = StringSubstitutor.createInterpolator();
            substitutor.setEnableUndefinedVariableException(true);
            String owner = substitutor.replace(directive).trim();
            if (owner.isEmpty()) {
                throw new PreviewDeniedException();
            }
            return owner;
        } catch (IllegalArgumentException e) {
            throw new PreviewDeniedException();
        }
    }
}
