package com.otterworks.ottershops.warehouse;

import org.springframework.stereotype.Component;

/** Stand-in for the 3PL SFTP drop: applies the partner's file spec and acks or rejects the whole file. */
@Component
public class MockThreePlGateway implements ThreePlGateway {
    @Override
    public Ack submit(String fileName, String csv) {
        String[] lines = csv.split("\n");
        if (lines.length == 0 || !lines[0].equals(WarehouseExportJob.HEADER)) {
            return new Ack(false, "E100 " + fileName + ": header does not match spec");
        }
        int expected = WarehouseExportJob.HEADER.split(",").length;
        for (int i = 1; i < lines.length; i++) {
            int fields = countFields(lines[i]);
            if (fields != expected) {
                return new Ack(false, "E210 " + fileName + " record " + (i + 1) + ": expected " + expected
                        + " fields, found " + fields);
            }
        }
        return new Ack(true, null);
    }

    /** RFC 4180 field count: commas inside double quotes don't split. */
    static int countFields(String line) {
        int fields = 1;
        boolean quoted = false;
        for (int i = 0; i < line.length(); i++) {
            char c = line.charAt(i);
            if (c == '"') quoted = !quoted;
            else if (c == ',' && !quoted) fields++;
        }
        return fields;
    }
}
