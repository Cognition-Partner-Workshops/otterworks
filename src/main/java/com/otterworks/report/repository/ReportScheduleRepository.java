package com.otterworks.report.repository;

import com.otterworks.report.model.ReportSchedule;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Date;
import java.util.List;

@Repository
public interface ReportScheduleRepository extends JpaRepository<ReportSchedule, Long> {

    List<ReportSchedule> findByEnabledTrueAndNextRunAtLessThanEqual(Date now);
}
