package com.bank.statements;

import java.util.regex.Pattern;
import javax.servlet.http.Cookie;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

/**
 * Remembers the last statement a browser opened in a cookie, so anonymous page views
 * never create a server-side session.
 */
final class LastViewed {
    static final String COOKIE = "lastAccount";
    private static final Pattern ACCOUNT = Pattern.compile("[A-Z0-9]{8,20}");

    private LastViewed() {
    }

    static boolean isAccount(String s) {
        return s != null && ACCOUNT.matcher(s).matches();
    }

    static String read(HttpServletRequest req) {
        Cookie[] cookies = req.getCookies();
        if (cookies == null) {
            return null;
        }
        for (Cookie c : cookies) {
            if (COOKIE.equals(c.getName()) && isAccount(c.getValue())) {
                return c.getValue();
            }
        }
        return null;
    }

    static void remember(HttpServletRequest req, HttpServletResponse resp, String account) {
        Cookie c = new Cookie(COOKIE, account);
        String path = req.getContextPath();
        c.setPath(path == null || path.isEmpty() ? "/" : path);
        c.setHttpOnly(true);
        c.setSecure(req.isSecure());
        resp.addCookie(c);
    }
}
