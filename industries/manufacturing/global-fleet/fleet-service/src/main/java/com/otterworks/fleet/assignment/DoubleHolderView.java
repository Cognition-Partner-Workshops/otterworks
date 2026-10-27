package com.otterworks.fleet.assignment;

import java.util.List;

public record DoubleHolderView(
        String employeeNo,
        String employmentLegacyRef,
        String source,
        List<DoubleHolderAssignmentView> assignments) {
}
