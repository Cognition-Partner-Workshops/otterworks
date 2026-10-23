package com.otterworks.report.controller;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;

/**
 * Serves the Prometheus scrape at {@code /metrics}, the path the Helm ServiceMonitor scrapes.
 */
@Controller
public class MetricsController {

    @GetMapping("/metrics")
    public String metrics() {
        return "forward:/actuator/prometheus";
    }
}
