package example.claimshub;

/**
 * Every BizTalk orchestration becomes one Camel route, {@code direct:orchestration.<Name>}, with route id
 * {@code orchestration.<Name>}. The body in is the message the activating receive took.
 */
public final class OrchestrationEndpoints {

    public static final String PREFIX = "direct:orchestration.";

    private OrchestrationEndpoints() {
    }

    public static String of(String orchestration) {
        return PREFIX + orchestration;
    }

    public static String routeId(String orchestration) {
        return "orchestration." + orchestration;
    }
}
