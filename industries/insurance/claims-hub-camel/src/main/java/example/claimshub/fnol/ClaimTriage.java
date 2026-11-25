package example.claimshub.fnol;

/** The Call_Rules shape: runs the ClaimTriage policy over a TriageFacts document. */
public interface ClaimTriage {

    TriageResult evaluate(String claimNumber, String triageFacts);
}
