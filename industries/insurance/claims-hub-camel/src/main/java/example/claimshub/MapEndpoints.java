package example.claimshub;

/**
 * Every BizTalk map is exposed as one Camel route, {@code direct:map.<MapName>}, whose body in is the
 * source message, whose route id is {@code map.<MapName>} and whose body out is the target message. The golden tests drive maps through these
 * endpoints, so a map is done when its route exists and its golden test is green.
 */
public final class MapEndpoints {

    public static final String PREFIX = "direct:map.";

    private MapEndpoints() {
    }

    public static String of(String mapName) {
        return PREFIX + mapName;
    }

    public static String routeId(String mapName) {
        return "map." + mapName;
    }
}
