package com.otterworks.report.preview;

/**
 * The caller is not authorized to preview the requested template.
 */
public class PreviewDeniedException extends RuntimeException {

    public PreviewDeniedException() {
        super("template preview denied");
    }
}
