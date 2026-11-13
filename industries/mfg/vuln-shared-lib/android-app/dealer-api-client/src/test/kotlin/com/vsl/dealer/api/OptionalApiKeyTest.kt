package com.vsl.dealer.api

import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.assertNull
import org.junit.Test

class OptionalApiKeyTest {
    @Test fun absentOrBlankApiKeyDoesNotSendHeader() = runBlocking {
        val server = MockWebServer()
        server.start()
        try {
            val tokens = object : TokenStore {
                override fun read(): String? = null
                override fun write(token: String) {}
                override fun clear() {}
            }
            for (key in listOf(null, "", "  ")) {
                server.enqueue(MockResponse().setHeader("Content-Type", "application/json").setBody("[]"))
                DealerRepository.create(server.url("/").toString(), key, tokens).inventory("D-1001")
                assertNull(server.takeRequest().getHeader("X-Api-Key"))
            }
        } finally { server.shutdown() }
    }
}
