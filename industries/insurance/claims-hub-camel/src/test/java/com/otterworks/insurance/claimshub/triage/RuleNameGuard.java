package com.otterworks.insurance.claimshub.triage;

import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.TreeSet;

/** Names the rules that are in one of the rules table and the BRE export but not the other. */
final class RuleNameGuard {

    private RuleNameGuard() {
    }

    static List<String> differences(Collection<String> table, Collection<String> bre) {
        List<String> problems = new ArrayList<>();
        TreeSet<String> onlyInTable = new TreeSet<>(table);
        onlyInTable.removeAll(bre);
        TreeSet<String> onlyInBre = new TreeSet<>(bre);
        onlyInBre.removeAll(table);
        onlyInTable.forEach(n -> problems.add("in the rules table but not the BRE export: " + n));
        onlyInBre.forEach(n -> problems.add("in the BRE export but not the rules table: " + n));
        return problems;
    }
}
