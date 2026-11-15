package com.otterworks.commission.common;

import java.sql.SQLException;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.springframework.dao.DataAccessException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/**
 * Error contract with the COMMISSION_PKG delegate: any rejection is HTTP 422 with
 * {"ora_code": -NNNNN, "message": "..."}. Rule rejections carry the ORA-20xxx the
 * package used to raise; database errors (constraint, NOT NULL, date format)
 * carry Oracle's own code and the first line of its message without the prefix.
 */
@RestControllerAdvice
public class OraErrorAdvice {

    private static final Pattern ORA_LINE = Pattern.compile("^ORA-(\\d{5}): (.*)$");

    @ExceptionHandler(OraException.class)
    public ResponseEntity<Map<String, Object>> rule(OraException e) {
        return body(e.oraCode(), e.getMessage());
    }

    @ExceptionHandler(DataAccessException.class)
    public ResponseEntity<Map<String, Object>> database(DataAccessException e) {
        SQLException sql = findSqlException(e);
        if (sql == null) {
            return body(-20000, e.getMostSpecificCause().getMessage());
        }
        OraException ora = fromSqlException(sql);
        return body(ora.oraCode(), ora.getMessage());
    }

    /** Maps a driver exception to the code and first-line message Oracle reported. */
    public static OraException fromSqlException(SQLException sql) {
        String first = firstLine(sql.getMessage());
        Matcher m = ORA_LINE.matcher(first);
        if (m.matches()) {
            return new OraException(-Integer.parseInt(m.group(1)), m.group(2));
        }
        return new OraException(sql.getErrorCode() == 0 ? -20000 : -sql.getErrorCode(), first);
    }

    private static SQLException findSqlException(Throwable t) {
        for (Throwable c = t; c != null; c = c.getCause()) {
            if (c instanceof SQLException s) {
                return s;
            }
        }
        return null;
    }

    private static String firstLine(String s) {
        if (s == null) {
            return "";
        }
        int nl = s.indexOf('\n');
        return nl < 0 ? s : s.substring(0, nl);
    }

    private static ResponseEntity<Map<String, Object>> body(int code, String message) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("ora_code", code);
        m.put("message", message);
        return ResponseEntity.status(HttpStatus.UNPROCESSABLE_ENTITY).body(m);
    }
}
