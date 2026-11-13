package com.vsl.dealer

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vsl.dealer.api.Claim
import com.vsl.dealer.api.DealerClient
import com.vsl.dealer.api.InventoryItem
import com.vsl.dealer.api.SignInResponse
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class SignInState(
    val email: String = "",
    val password: String = "",
    val busy: Boolean = false,
    val error: String? = null,
    val session: SignInResponse? = null,
)

class SignInViewModel(private val client: DealerClient) : ViewModel() {
    private val mutableState = MutableStateFlow(SignInState())
    val state = mutableState.asStateFlow()

    fun emailChanged(value: String) {
        mutableState.value = mutableState.value.copy(email = value, error = null)
    }

    fun passwordChanged(value: String) {
        mutableState.value = mutableState.value.copy(password = value, error = null)
    }

    fun signIn() {
        val current = mutableState.value
        if (current.busy) return
        if (current.email.isBlank() || current.password.isBlank()) {
            mutableState.value = current.copy(error = "Enter your email and password.")
            return
        }
        mutableState.value = current.copy(busy = true, error = null)
        viewModelScope.launch {
            try {
                val session = client.signIn(current.email.trim(), current.password)
                mutableState.value = mutableState.value.copy(
                    busy = false, password = "", session = session,
                )
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                mutableState.value = mutableState.value.copy(
                    busy = false, error = "Sign in could not be completed. Please try again.",
                )
            }
        }
    }
}

data class ListState<T>(
    val items: List<T> = emptyList(),
    val loading: Boolean = false,
    val error: String? = null,
)

class InventoryViewModel(private val client: DealerClient) : ViewModel() {
    private val mutableState = MutableStateFlow(ListState<InventoryItem>())
    val state = mutableState.asStateFlow()

    fun load(dealerId: String) {
        if (mutableState.value.loading) return
        mutableState.value = mutableState.value.copy(loading = true, error = null)
        viewModelScope.launch {
            try {
                mutableState.value = ListState(items = client.inventory(dealerId))
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                mutableState.value = mutableState.value.copy(
                    loading = false, error = "Inventory is unavailable. Please retry.",
                )
            }
        }
    }
}

class ClaimsViewModel(private val client: DealerClient) : ViewModel() {
    private val mutableState = MutableStateFlow(ListState<Claim>())
    val state = mutableState.asStateFlow()

    fun load(dealerId: String) {
        if (mutableState.value.loading) return
        mutableState.value = mutableState.value.copy(loading = true, error = null)
        viewModelScope.launch {
            try {
                mutableState.value = ListState(items = client.claims(dealerId))
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                mutableState.value = mutableState.value.copy(
                    loading = false, error = "Claims are unavailable. Please retry.",
                )
            }
        }
    }
}

data class SubmitClaimState(
    val vin: String = "",
    val description: String = "",
    val busy: Boolean = false,
    val error: String? = null,
    val submitted: Claim? = null,
)

class SubmitClaimViewModel(private val client: DealerClient) : ViewModel() {
    private val mutableState = MutableStateFlow(SubmitClaimState())
    val state = mutableState.asStateFlow()

    fun vinChanged(value: String) {
        mutableState.value = mutableState.value.copy(vin = value, error = null)
    }

    fun descriptionChanged(value: String) {
        mutableState.value = mutableState.value.copy(description = value, error = null)
    }

    fun submit() {
        val current = mutableState.value
        if (current.busy) return
        if (current.vin.isBlank() || current.description.isBlank()) {
            mutableState.value = current.copy(error = "Enter a VIN and description.")
            return
        }
        mutableState.value = current.copy(busy = true, error = null)
        viewModelScope.launch {
            try {
                val claim = client.submitClaim(current.vin.trim(), current.description.trim())
                mutableState.value = current.copy(submitted = claim)
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                mutableState.value = mutableState.value.copy(
                    busy = false, error = "The claim was not submitted. Please retry.",
                )
            }
        }
    }
}
