package com.otterworks.ottershops.ops;

import com.otterworks.ottershops.common.ApiException;
import java.security.MessageDigest;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/ops")
public class OpsController {
    private final String opsKey;
    private final JobRunRepository runs;
    private final Map<String, Runnable> jobs;

    public OpsController(@Value("${ottershops.ops.api-key:}") String opsKey, JobRunRepository runs,
                         PriceFeedJob priceFeed) {
        this.opsKey = opsKey;
        this.runs = runs;
        this.jobs = Map.of(PriceFeedJob.JOB, priceFeed::run);
    }

    @GetMapping("/jobs/runs")
    public List<JobRunRepository.JobRun> runs(@RequestHeader(value = "X-Ops-Key", required = false) String key,
                                              @RequestParam(required = false) String job) {
        check(key);
        return runs.recent(job, 50);
    }

    @PostMapping("/jobs/{job}/run")
    public List<JobRunRepository.JobRun> run(@RequestHeader(value = "X-Ops-Key", required = false) String key,
                                             @PathVariable String job) {
        check(key);
        Runnable r = jobs.get(job);
        if (r == null) throw ApiException.notFound("Job");
        r.run();
        return runs.recent(job, 10);
    }

    private void check(String key) {
        if (opsKey.isBlank() || key == null
                || !MessageDigest.isEqual(opsKey.getBytes(StandardCharsets.UTF_8), key.getBytes(StandardCharsets.UTF_8))) {
            throw new ApiException(HttpStatus.FORBIDDEN, "FORBIDDEN", "Ops key required");
        }
    }
}
