package com.vsl.dealer

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.vsl.dealer.api.DealerClient
import com.vsl.dealer.api.SignInResponse
import java.text.NumberFormat
import java.util.Locale

@Composable
fun DealerApp(client: DealerClient) {
    val navigation = rememberNavController()
    var dealerId by rememberSaveable { mutableStateOf("") }
    NavHost(navigation, startDestination = "signin") {
        composable("signin") {
            val model = viewModel { SignInViewModel(client) }
            SignInScreen(model) { session ->
                dealerId = session.dealerId
                navigation.navigate("inventory") { popUpTo("signin") { inclusive = true } }
            }
        }
        composable("inventory") {
            val model = viewModel { InventoryViewModel(client) }
            val state by model.state.collectAsStateWithLifecycle()
            LaunchedEffect(dealerId) { model.load(dealerId) }
            Workspace("Inventory · $dealerId", onClaims = { navigation.navigate("claims") }) {
                ListFeedback(state.loading, state.error, state.items.isEmpty(), "No vehicles available.") {
                    model.load(dealerId)
                }
                LazyColumn(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    items(state.items, key = { it.vin }) { vehicle ->
                        Card(Modifier.fillMaxWidth()) {
                            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text("${vehicle.year} ${vehicle.model}", style = MaterialTheme.typography.titleMedium)
                                Text(vehicle.vin)
                                Text(vehicle.status)
                                Text(NumberFormat.getCurrencyInstance(Locale.US).format(vehicle.priceCents / 100.0))
                            }
                        }
                    }
                }
            }
        }
        composable("claims") {
            val model = viewModel { ClaimsViewModel(client) }
            val state by model.state.collectAsStateWithLifecycle()
            LaunchedEffect(dealerId) { model.load(dealerId) }
            Workspace("Warranty claims", onInventory = { navigation.popBackStack("inventory", false) }) {
                Button(onClick = { navigation.navigate("submit") }) { Text("New claim") }
                ListFeedback(state.loading, state.error, state.items.isEmpty(), "No claims yet.") {
                    model.load(dealerId)
                }
                LazyColumn(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    items(state.items, key = { it.id }) { claim ->
                        Card(Modifier.fillMaxWidth()) {
                            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text(claim.id, style = MaterialTheme.typography.titleMedium)
                                Text(claim.vin)
                                Text(claim.status)
                                Text(claim.description)
                                Text(claim.submittedAt)
                            }
                        }
                    }
                }
            }
        }
        composable("submit") {
            val model = viewModel { SubmitClaimViewModel(client) }
            val state by model.state.collectAsStateWithLifecycle()
            LaunchedEffect(state.submitted) {
                if (state.submitted != null) navigation.popBackStack()
            }
            Workspace("Submit a claim", onClaims = { navigation.popBackStack() }) {
                OutlinedTextField(
                    state.vin, model::vinChanged, label = { Text("VIN") },
                    singleLine = true, modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    state.description, model::descriptionChanged, label = { Text("Description") },
                    minLines = 4, modifier = Modifier.fillMaxWidth(),
                )
                state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                Button(onClick = model::submit, enabled = !state.busy) {
                    Text(if (state.busy) "Submitting…" else "Submit claim")
                }
            }
        }
    }
}

@Composable
fun SignInScreen(model: SignInViewModel, onSignedIn: (SignInResponse) -> Unit) {
    val state by model.state.collectAsStateWithLifecycle()
    LaunchedEffect(state.session) { state.session?.let(onSignedIn) }
    Workspace("Dealer workspace") {
        Text("Sign in to view inventory and manage warranty claims.")
        OutlinedTextField(
            state.email, model::emailChanged, label = { Text("Email") },
            singleLine = true, modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            state.password, model::passwordChanged, label = { Text("Password") },
            visualTransformation = PasswordVisualTransformation(),
            singleLine = true, modifier = Modifier.fillMaxWidth(),
        )
        state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        Button(onClick = model::signIn, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) {
            Text(if (state.busy) "Signing in…" else "Sign in")
        }
    }
}

@Composable
private fun Workspace(
    title: String,
    onInventory: (() -> Unit)? = null,
    onClaims: (() -> Unit)? = null,
    content: @Composable () -> Unit,
) {
    Column(
        Modifier.fillMaxSize().padding(PaddingValues(horizontal = 24.dp, vertical = 48.dp)),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text(title, style = MaterialTheme.typography.headlineMedium)
        onInventory?.let { OutlinedButton(onClick = it) { Text("Inventory") } }
        onClaims?.let { OutlinedButton(onClick = it) { Text("Claims") } }
        content()
    }
}

@Composable
private fun ListFeedback(
    loading: Boolean,
    error: String?,
    empty: Boolean,
    emptyMessage: String,
    retry: () -> Unit,
) {
    when {
        loading -> CircularProgressIndicator()
        error != null -> {
            Text(error, color = MaterialTheme.colorScheme.error)
            OutlinedButton(onClick = retry) { Text("Retry") }
        }
        empty -> Text(emptyMessage)
    }
}
