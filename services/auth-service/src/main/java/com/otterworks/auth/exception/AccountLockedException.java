package com.otterworks.auth.exception;

import java.time.Instant;

public class AccountLockedException extends RuntimeException {

  private final Instant lockedUntil;

  public AccountLockedException(Instant lockedUntil) {
    super("Account temporarily locked after repeated failed login attempts");
    this.lockedUntil = lockedUntil;
  }

  public Instant getLockedUntil() {
    return lockedUntil;
  }
}
