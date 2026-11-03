package com.otterworks.legacyportal.common;

import java.util.List;
import javax.servlet.http.HttpServletRequest;
import org.springframework.core.MethodParameter;
import org.springframework.stereotype.Component;
import org.springframework.web.bind.support.WebDataBinderFactory;
import org.springframework.web.context.request.NativeWebRequest;
import org.springframework.web.method.support.HandlerMethodArgumentResolver;
import org.springframework.web.method.support.ModelAndViewContainer;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * Lets controllers declare a {@link PortalPrincipal} parameter. Resolution runs {@link
 * PortalAuthenticator}, so an unauthenticated request never reaches the handler body.
 */
@Component
public class PortalPrincipalArgumentResolver
        implements HandlerMethodArgumentResolver, WebMvcConfigurer {

    private final PortalAuthenticator authenticator;

    public PortalPrincipalArgumentResolver(PortalAuthenticator authenticator) {
        this.authenticator = authenticator;
    }

    @Override
    public void addArgumentResolvers(List<HandlerMethodArgumentResolver> resolvers) {
        resolvers.add(this);
    }

    @Override
    public boolean supportsParameter(MethodParameter parameter) {
        return PortalPrincipal.class.equals(parameter.getParameterType());
    }

    @Override
    public Object resolveArgument(
            MethodParameter parameter,
            ModelAndViewContainer mavContainer,
            NativeWebRequest webRequest,
            WebDataBinderFactory binderFactory) {
        HttpServletRequest request = webRequest.getNativeRequest(HttpServletRequest.class);
        return authenticator.authenticate(request);
    }
}
