package com.otterworks.fleet.eligibility;

import com.otterworks.fleet.domain.Person;
import java.util.List;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;
import org.springframework.data.repository.query.Param;

public interface EmployeeSearchRepository extends Repository<Person, Long> {

    @Query("""
            select p from Person p
            where lower(p.employeeNo) like :pattern escape '\\'
               or lower(p.lastName) like :pattern escape '\\'
               or lower(p.firstName) like :pattern escape '\\'
            order by p.lastName, p.firstName, p.employeeNo
            """)
    List<Person> search(@Param("pattern") String pattern, Pageable pageable);
}
