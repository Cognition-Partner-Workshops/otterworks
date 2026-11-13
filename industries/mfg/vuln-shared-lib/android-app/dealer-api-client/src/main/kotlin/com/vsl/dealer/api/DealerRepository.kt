package com.vsl.dealer.api

import kotlinx.serialization.json.Json
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Response
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Query

interface DealerApi {
    @POST("api/identity/signin")
    suspend fun signIn(@Body request: SignInRequest): SignInResponse

    @GET("api/dealer/inventory")
    suspend fun inventory(@Query("dealerId") dealerId: String): List<InventoryItem>

    @GET("api/warranty/claims")
    suspend fun claims(@Query("dealerId") dealerId: String): List<Claim>

    @POST("api/warranty/claims")
    suspend fun submitClaim(@Body request: SubmitClaimRequest): Claim
}

class BearerInterceptor(private val tokens: TokenStore) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()
        val path = request.url.encodedPath
        val dealerCall = path.startsWith("/api/dealer/") || path.startsWith("/api/warranty/")
        val token = if (dealerCall) tokens.read() else null
        val outgoing = request.newBuilder().apply {
            if (!token.isNullOrBlank()) header("Authorization", "Bearer $token")
        }.build()
        return chain.proceed(outgoing)
    }
}

class ApiKeyInterceptor(private val apiKey: String) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response =
        chain.proceed(chain.request().newBuilder().header("X-Api-Key", apiKey).build())
}

class DealerRepository(
    private val api: DealerApi,
    private val tokens: TokenStore,
) : DealerClient {
    override suspend fun signIn(email: String, password: String): SignInResponse {
        val session = api.signIn(SignInRequest(email, password))
        tokens.write(session.accessToken)
        return session
    }

    override suspend fun inventory(dealerId: String): List<InventoryItem> = api.inventory(dealerId)
    override suspend fun claims(dealerId: String): List<Claim> = api.claims(dealerId)
    override suspend fun submitClaim(vin: String, description: String): Claim =
        api.submitClaim(SubmitClaimRequest(vin, description))

    companion object {
        fun create(baseUrl: String, apiKey: String, tokens: TokenStore): DealerRepository {
            val client = OkHttpClient.Builder()
                .addInterceptor(BearerInterceptor(tokens))
                .addInterceptor(ApiKeyInterceptor(apiKey))
                .build()
            val json = Json { ignoreUnknownKeys = true }
            val api = Retrofit.Builder()
                .baseUrl(baseUrl)
                .client(client)
                .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
                .build()
                .create(DealerApi::class.java)
            return DealerRepository(api, tokens)
        }
    }
}
