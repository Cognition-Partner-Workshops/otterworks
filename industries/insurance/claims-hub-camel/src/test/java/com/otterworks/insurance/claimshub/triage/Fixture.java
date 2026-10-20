package com.otterworks.insurance.claimshub.triage;

import java.nio.file.Path;

final class Fixture {

    static final Path ROOT = Path.of(System.getProperty("fixture.dir", "../biztalk-claims-intake"));
    static final Path POLICY = ROOT.resolve("Rules/ClaimTriagePolicy.xml");
    static final Path FACTS = ROOT.resolve("corpus/golden/triage-facts");
    static final Path REFERENCE_RESULTS = ROOT.resolve("corpus/golden/triage");
    static final String TABLE = "rules/claim-triage.csv";

    private Fixture() {
    }
}
