package com.otterworks.notification.routes

import com.otterworks.notification.plugins.WS_AUTH
import com.otterworks.notification.plugins.authenticatedUserId
import com.otterworks.notification.websocket.WebSocketManager
import io.ktor.http.HttpStatusCode
import io.ktor.server.application.call
import io.ktor.server.application.createRouteScopedPlugin
import io.ktor.server.application.install
import io.ktor.server.auth.AuthenticationChecked
import io.ktor.server.auth.authenticate
import io.ktor.server.auth.jwt.JWTPrincipal
import io.ktor.server.auth.principal
import io.ktor.server.response.respond
import io.ktor.server.routing.Route
import io.ktor.server.routing.route
import io.ktor.server.websocket.DefaultWebSocketServerSession
import io.ktor.server.websocket.webSocket
import io.ktor.websocket.CloseReason
import io.ktor.websocket.Frame
import io.ktor.websocket.close
import io.ktor.websocket.readText

/** Rejects the upgrade when a legacy `{userId}` path segment names anyone but the token's subject. */
private val RequirePathUserIsPrincipal = createRouteScopedPlugin("RequirePathUserIsPrincipal") {
    on(AuthenticationChecked) { call ->
        val pathUserId = call.parameters["userId"] ?: return@on
        val principalUserId = call.principal<JWTPrincipal>()?.authenticatedUserId() ?: return@on
        if (pathUserId != principalUserId) {
            call.respond(HttpStatusCode.Forbidden, ErrorResponse("cannot subscribe to another user's notifications"))
        }
    }
}

/**
 * Real-time notification stream for the authenticated user. The subscription is always keyed by the
 * token's subject; `/ws/notifications/{userId}` is kept for existing clients and must match it.
 */
fun Route.notificationWebSocket(webSocketManager: WebSocketManager) {
    authenticate(WS_AUTH) {
        webSocket("/ws/notifications") { streamNotifications(webSocketManager) }
        route("/ws/notifications/{userId}") {
            install(RequirePathUserIsPrincipal)
            webSocket { streamNotifications(webSocketManager) }
        }
    }
}

private suspend fun DefaultWebSocketServerSession.streamNotifications(webSocketManager: WebSocketManager) {
    val userId = call.principal<JWTPrincipal>()?.authenticatedUserId()
    if (userId == null) {
        close(CloseReason(CloseReason.Codes.VIOLATED_POLICY, "authentication required"))
        return
    }

    webSocketManager.addConnection(userId, this)

    try {
        for (frame in incoming) {
            when (frame) {
                is Frame.Text -> {
                    if (frame.readText() == "ping") {
                        send(Frame.Text("pong"))
                    }
                }
                is Frame.Close -> break
                else -> { /* ignore other frame types */ }
            }
        }
    } finally {
        webSocketManager.removeConnection(userId, this)
    }
}
