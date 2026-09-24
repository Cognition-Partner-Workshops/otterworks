package com.otterworks.report.repository;

import com.otterworks.report.model.ReportSchedule;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.List;

public interface ReportScheduleRepository extends JpaRepository<ReportSchedule, Long> {

    List<ReportSchedule> findByEnabledTrueAndNextRunAtLessThanEqual(Instant now);

    /**
     * Atomically claims a due schedule: advances {@code nextRunAt} and bumps the version only if the
     * row is still at the version and {@code nextRunAt} the caller observed. Returns 1 when this
     * instance won the claim, 0 when another instance already ran it.
     */
    @Transactional
    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Query("""
            UPDATE ReportSchedule s
               SET s.nextRunAt = :nextRunAt,
                   s.lastRunAt = :now,
                   s.version = s.version + 1
             WHERE s.id = :id
               AND s.version = :expectedVersion
               AND s.nextRunAt = :expectedNextRunAt
               AND s.enabled = true
            """)
    int claimRun(@Param("id") Long id,
                 @Param("expectedVersion") long expectedVersion,
                 @Param("expectedNextRunAt") Instant expectedNextRunAt,
                 @Param("now") Instant now,
                 @Param("nextRunAt") Instant nextRunAt);
}
