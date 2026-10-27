package com.otterworks.fleet.domain;

import org.springframework.data.jpa.repository.JpaRepository;

public interface PersonRepository extends JpaRepository<Person, Long> {

    java.util.Optional<Person> findByEmployeeNo(String employeeNo);

    java.util.List<Person> findTop50ByOrderByLastNameAscFirstNameAscEmployeeNoAsc();

    java.util.List<Person> findAllByOrderByLastNameAscFirstNameAscEmployeeNoAsc(
            org.springframework.data.domain.Pageable pageable);
}
