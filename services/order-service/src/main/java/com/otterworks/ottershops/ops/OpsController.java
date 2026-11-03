package com.otterworks.ottershops.ops;

import com.otterworks.ottershops.common.ApiException;
import com.otterworks.ottershops.warehouse.WarehouseExportJob;
import java.util.List;
import java.util.Map;
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
    private final OpsAuth auth;
    private final JobRunRepository runs;
    private final Map<String, Runnable> jobs;

    public OpsController(OpsAuth auth, JobRunRepository runs, PriceFeedJob priceFeed, PickupReadyJob pickupReady,
                         WarehouseExportJob warehouseExport) {
        this.auth = auth;
        this.runs = runs;
        this.jobs = Map.of(PriceFeedJob.JOB, priceFeed::run, PickupReadyJob.JOB, pickupReady::run,
                WarehouseExportJob.JOB, warehouseExport::run);
    }

    @GetMapping("/jobs/runs")
    public List<JobRunRepository.JobRun> runs(@RequestHeader(value = "X-Ops-Key", required = false) String key,
                                              @RequestParam(required = false) String job) {
        auth.check(key);
        return runs.recent(job, 50);
    }

    @PostMapping("/jobs/{job}/run")
    public List<JobRunRepository.JobRun> run(@RequestHeader(value = "X-Ops-Key", required = false) String key,
                                             @PathVariable String job) {
        auth.check(key);
        Runnable r = jobs.get(job);
        if (r == null) throw ApiException.notFound("Job");
        r.run();
        return runs.recent(job, 10);
    }
}
