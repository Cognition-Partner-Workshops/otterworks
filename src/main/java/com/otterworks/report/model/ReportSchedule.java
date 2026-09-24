package com.otterworks.report.model;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Lob;
import jakarta.persistence.Table;
import jakarta.persistence.Temporal;
import jakarta.persistence.TemporalType;
import jakarta.persistence.Version;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.util.Date;

@Entity
@Table(name = "report_schedules")
public class ReportSchedule {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @NotBlank
    @Column(name = "name", nullable = false)
    private String name;

    @NotBlank
    @Column(name = "cron_expression", nullable = false)
    private String cronExpression;

    @NotBlank
    @Column(name = "time_zone", nullable = false)
    private String timeZone;

    @NotNull
    @Lob
    @Column(name = "template", nullable = false)
    private String template;

    @NotBlank
    @Column(name = "requested_by", nullable = false)
    private String requestedBy;

    @Column(name = "enabled", nullable = false)
    private boolean enabled = true;

    @Temporal(TemporalType.TIMESTAMP)
    @Column(name = "created_at", nullable = false)
    private Date createdAt;

    @Temporal(TemporalType.TIMESTAMP)
    @Column(name = "last_run_at")
    private Date lastRunAt;

    @Temporal(TemporalType.TIMESTAMP)
    @Column(name = "next_run_at")
    private Date nextRunAt;

    @Version
    private Long version;

    public ReportSchedule() {
    }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public String getCronExpression() { return cronExpression; }
    public void setCronExpression(String cronExpression) { this.cronExpression = cronExpression; }
    public String getTimeZone() { return timeZone; }
    public void setTimeZone(String timeZone) { this.timeZone = timeZone; }
    public String getTemplate() { return template; }
    public void setTemplate(String template) { this.template = template; }
    public String getRequestedBy() { return requestedBy; }
    public void setRequestedBy(String requestedBy) { this.requestedBy = requestedBy; }
    public boolean isEnabled() { return enabled; }
    public void setEnabled(boolean enabled) { this.enabled = enabled; }
    public Date getCreatedAt() { return createdAt; }
    public void setCreatedAt(Date createdAt) { this.createdAt = createdAt; }
    public Date getLastRunAt() { return lastRunAt; }
    public void setLastRunAt(Date lastRunAt) { this.lastRunAt = lastRunAt; }
    public Date getNextRunAt() { return nextRunAt; }
    public void setNextRunAt(Date nextRunAt) { this.nextRunAt = nextRunAt; }
    public Long getVersion() { return version; }
    public void setVersion(Long version) { this.version = version; }
}
