package com.otterworks.notification.plugins

import com.auth0.jwt.JWT
import com.auth0.jwt.JWTVerifier
import com.auth0.jwt.algorithms.Algorithm
import com.auth0.jwt.exceptions.JWTDecodeException
import com.otterworks.notification.config.AppConfig
import com.otterworks.notification.routes.ErrorResponse
import io.ktor.http.HttpStatusCode
import io.ktor.http.auth.HttpAuthHeader
import io.ktor.server.application.Application
import io.ktor.server.application.ApplicationCall
import io.ktor.server.application.call
import io.ktor.server.application.install
import io.ktor.server.auth.Authentication
import io.ktor.server.auth.jwt.JWTPrincipal
import io.ktor.server.auth.jwt.jwt
import io.ktor.server.auth.parseAuthorizationHeader
import io.ktor.server.response.respond
import mu.KotlinLogging

private val logger = KotlinLogging.logger {}

const val WS_AUTH = "notification-ws-jwt"

/** Query parameter accepted for the token on WebSocket upgrades, since browsers cannot set headers there. */
const val ACCESS_TOKEN_QUERY_PARAM = "access_token"

/**
 * Validates the HMAC-signed access tokens minted by auth-service with the shared JWT_SECRET.
 * auth-service lets jjwt pick HS256/384/512 from the key length, so all three are accepted.
 * With no secret configured every request is rejected.
 */
fun Application.configureSecurity(config: AppConfig) {
    val secret = config.jwtSecret
    if (secret == null) {
        logger.warn { "JWT_SECRET is not set; authenticated notification routes will reject every request" }
    }

    install(Authentication) {
        jwt(WS_AUTH) {
            realm = "otterworks-notifications"
            authHeader { call -> bearerTokenFrom(call) }
            verifier { authHeader -> secret?.let { hmacVerifierFor(authHeader, it) } }
            validate { credential ->
                val principal = JWTPrincipal(credential.payload)
                val isRefreshToken = credential.payload.getClaim("type").asString() == "refresh"
                if (!isRefreshToken && principal.authenticatedUserId() != null) principal else null
            }
            challenge { _, _ ->
                call.respond(HttpStatusCode.Unauthorized, ErrorResponse("missing or invalid access token"))
            }
        }
    }
}

/** The user the token was issued to: the standard `sub` claim, falling back to `user_id` like api-gateway. */
fun JWTPrincipal.authenticatedUserId(): String? =
    (subject ?: payload.getClaim("user_id").asString())?.takeIf { it.isNotBlank() }

private fun bearerTokenFrom(call: ApplicationCall): HttpAuthHeader? {
    val header = try {
        call.request.parseAuthorizationHeader()
    } catch (e: IllegalArgumentException) {
        null
    }
    if (header != null) return header

    val queryToken = call.request.queryParameters[ACCESS_TOKEN_QUERY_PARAM]
    return queryToken?.takeIf { it.isNotBlank() }?.let { HttpAuthHeader.Single("Bearer", it) }
}

private fun hmacVerifierFor(authHeader: HttpAuthHeader, secret: String): JWTVerifier? {
    val token = (authHeader as? HttpAuthHeader.Single)?.blob ?: return null
    val algorithmName = try {
        JWT.decode(token).algorithm
    } catch (e: JWTDecodeException) {
        return null
    }
    val algorithm = when (algorithmName) {
        "HS256" -> Algorithm.HMAC256(secret)
        "HS384" -> Algorithm.HMAC384(secret)
        "HS512" -> Algorithm.HMAC512(secret)
        else -> return null
    }
    return JWT.require(algorithm).build()
}
