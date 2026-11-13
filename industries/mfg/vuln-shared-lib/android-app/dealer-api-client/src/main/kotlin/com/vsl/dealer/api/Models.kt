package com.vsl.dealer.api

import kotlinx.serialization.Serializable

@Serializable
data class SignInRequest(val email: String, val password: String)

@Serializable
data class SignInResponse(
    val accessToken: String,
    val tokenType: String,
    val expiresIn: Long,
    val dealerId: String,
)

@Serializable
data class InventoryItem(
    val vin: String,
    val model: String,
    val year: Int,
    val status: String,
    val priceCents: Long,
    val imageUrl: String,
)

@Serializable
data class Claim(
    val id: String,
    val vin: String,
    val status: String,
    val description: String,
    val submittedAt: String,
)

@Serializable
data class SubmitClaimRequest(val vin: String, val description: String)

interface TokenStore {
    fun read(): String?
    fun write(token: String)
    fun clear()
}

interface DealerClient {
    suspend fun signIn(email: String, password: String): SignInResponse
    suspend fun inventory(dealerId: String): List<InventoryItem>
    suspend fun claims(dealerId: String): List<Claim>
    suspend fun submitClaim(vin: String, description: String): Claim
}
