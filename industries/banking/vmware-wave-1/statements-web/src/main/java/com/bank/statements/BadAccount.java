package com.bank.statements;

import java.io.IOException;
import javax.servlet.http.HttpServletResponse;

final class BadAccount {
    // Preserve the VM's public 400 response, including its historical footer.
    static final String BODY = "<!doctype html><html lang=\"en\"><head><title>HTTP Status 400 – Bad Request</title><style type=\"text/css\">body {font-family:Tahoma,Arial,sans-serif;} h1, h2, h3, b {color:white;background-color:#525D76;} h1 {font-size:22px;} h2 {font-size:16px;} h3 {font-size:14px;} p {font-size:12px;} a {color:black;} .line {height:1px;background-color:#525D76;border:none;}</style></head><body><h1>HTTP Status 400 – Bad Request</h1><hr class=\"line\" /><p><b>Type</b> Status Report</p><p><b>Message</b> account is required</p><p><b>Description</b> The server cannot or will not process the request due to something that is perceived to be a client error (e.g., malformed request syntax, invalid request message framing, or deceptive request routing).</p><hr class=\"line\" /><h3>Apache Tomcat/8.5.100</h3></body></html>";

    private BadAccount() {
    }

    static void respond(HttpServletResponse resp) throws IOException {
        resp.setStatus(HttpServletResponse.SC_BAD_REQUEST);
        resp.setContentType("text/html;charset=utf-8");
        resp.setHeader("Content-Language", "en");
        resp.getWriter().write(BODY);
    }
}
