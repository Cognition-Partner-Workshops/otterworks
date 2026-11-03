package com.otterworks.ottershops.ops;

import java.time.Instant;
import java.util.List;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class JobRunRepository {
    public record JobRun(long id, String job, String source, String status, int rowsRead, int rowsApplied,
                         String message, Instant startedAt, Instant finishedAt) {}

    private final JdbcTemplate jdbc;

    public JobRunRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public long start(String job, String source) {
        return jdbc.queryForObject("INSERT INTO job_runs (job, source, status) VALUES (?, ?, 'RUNNING') RETURNING id",
                Long.class, job, source);
    }

    public void finish(long id, String status, int read, int applied, String message) {
        jdbc.update("UPDATE job_runs SET status = ?, rows_read = ?, rows_applied = ?, message = ?, finished_at = now() WHERE id = ?",
                status, read, applied, message, id);
    }

    public boolean succeeded(String job, String source) {
        Integer n = jdbc.queryForObject("SELECT count(*) FROM job_runs WHERE job = ? AND source = ? AND status = 'SUCCEEDED'",
                Integer.class, job, source);
        return n != null && n > 0;
    }

    public List<JobRun> recent(String job, int limit) {
        return jdbc.query("""
                SELECT id, job, source, status, rows_read, rows_applied, message, started_at, finished_at FROM job_runs
                WHERE (?::text IS NULL OR job = ?) ORDER BY started_at DESC, id DESC LIMIT ?""",
                (rs, i) -> new JobRun(rs.getLong(1), rs.getString(2), rs.getString(3), rs.getString(4), rs.getInt(5),
                        rs.getInt(6), rs.getString(7), rs.getTimestamp(8).toInstant(),
                        rs.getTimestamp(9) == null ? null : rs.getTimestamp(9).toInstant()),
                job, job, limit);
    }
}
