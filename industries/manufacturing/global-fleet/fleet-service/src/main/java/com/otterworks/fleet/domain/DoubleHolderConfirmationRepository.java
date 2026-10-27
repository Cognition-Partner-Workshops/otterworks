package com.otterworks.fleet.domain;

import org.springframework.data.jpa.repository.JpaRepository;

public interface DoubleHolderConfirmationRepository
        extends JpaRepository<DoubleHolderConfirmation, String> {
}
