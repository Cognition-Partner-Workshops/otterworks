package com.otterworks.fleet.domain;

import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface CarRequestRepository extends JpaRepository<CarRequest, Long> {

    Optional<CarRequest> findBySubmissionKey(UUID submissionKey);
}
