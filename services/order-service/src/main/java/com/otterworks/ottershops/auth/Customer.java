package com.otterworks.ottershops.auth;

import java.time.Instant;
import java.util.UUID;

public record Customer(UUID id, String email, String firstName, String lastName, int rewardsPoints, Instant createdAt) {}
