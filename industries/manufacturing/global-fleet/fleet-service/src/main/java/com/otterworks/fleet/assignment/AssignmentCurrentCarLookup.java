package com.otterworks.fleet.assignment;

import com.otterworks.fleet.domain.AssignmentRepository;
import com.otterworks.fleet.eligibility.CurrentCarLookup;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.stereotype.Component;

@Component
public class AssignmentCurrentCarLookup implements CurrentCarLookup {

    private final AssignmentRepository assignmentRepository;

    public AssignmentCurrentCarLookup(AssignmentRepository assignmentRepository) {
        this.assignmentRepository = assignmentRepository;
    }

    @Override
    public Map<Long, String> currentRegistrations(Collection<Long> personIds) {
        if (personIds.isEmpty()) {
            return Map.of();
        }
        Map<Long, String> registrations = new LinkedHashMap<>();
        for (Object[] row : assignmentRepository.findCurrentRegistrations(personIds)) {
            registrations.putIfAbsent((Long) row[0], (String) row[1]);
        }
        return registrations;
    }
}
