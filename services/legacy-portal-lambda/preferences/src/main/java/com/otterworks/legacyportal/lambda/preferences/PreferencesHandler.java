package com.otterworks.legacyportal.lambda.preferences;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestHandler;
import com.amazonaws.services.lambda.runtime.events.APIGatewayV2HTTPEvent;
import com.amazonaws.services.lambda.runtime.events.APIGatewayV2HTTPResponse;
import java.util.Map;

public final class PreferencesHandler
        implements RequestHandler<APIGatewayV2HTTPEvent, APIGatewayV2HTTPResponse> {

    @Override
    public APIGatewayV2HTTPResponse handleRequest(APIGatewayV2HTTPEvent event, Context context) {
        String method = null;
        if (event != null
                && event.getRequestContext() != null
                && event.getRequestContext().getHttp() != null) {
            method = event.getRequestContext().getHttp().getMethod();
        }
        PreferenceRouter.Response response =
                RouterHolder.ROUTER.route(
                        method,
                        event == null ? null : event.getRawPath(),
                        event == null ? Map.of() : event.getHeaders(),
                        event == null ? null : event.getBody(),
                        event != null && Boolean.TRUE.equals(event.getIsBase64Encoded()));
        return APIGatewayV2HTTPResponse.builder()
                .withStatusCode(response.statusCode())
                .withHeaders(response.headers())
                .withBody(response.body())
                .withIsBase64Encoded(false)
                .build();
    }

    private static class RouterHolder {
        private static final PreferenceRouter ROUTER =
                new PreferenceRouter(
                        DataApiPreferenceRepository.fromEnvironment(),
                        "1".equals(System.getenv("FAIL_READS")));
    }
}
