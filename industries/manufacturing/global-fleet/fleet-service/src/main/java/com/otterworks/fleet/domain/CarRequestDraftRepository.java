package com.otterworks.fleet.domain;

import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface CarRequestDraftRepository extends JpaRepository<CarRequestDraft, UUID> {

    Optional<CarRequestDraft> findByPerson_Id(Long personId);
}
