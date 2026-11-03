package com.otterworks.ottershops.warehouse;

public interface ThreePlGateway {
    record Ack(boolean accepted, String error) {}

    Ack submit(String fileName, String csv);
}
