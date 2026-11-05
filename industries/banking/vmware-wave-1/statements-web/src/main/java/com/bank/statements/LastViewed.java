package com.bank.statements;

import javax.servlet.http.Cookie;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

final class LastViewed {
    private static final String NAME = "statementsLastAccount";

    private LastViewed() {
    }

    static boolean valid(String account) {
        return account != null && account.matches("[A-Z0-9]{8,20}");
    }

    static String read(HttpServletRequest req) {
        if (System.getenv("DB_URL") == null) {
            return (String) req.getSession(true).getAttribute("lastAccount");
        }
        return fromCookies(req.getCookies());
    }

    static String fromCookies(Cookie[] cookies) {
        if (cookies != null) {
            for (Cookie cookie : cookies) {
                if (NAME.equals(cookie.getName()) && valid(cookie.getValue())) {
                    return cookie.getValue();
                }
            }
        }
        return null;
    }

    static void write(HttpServletRequest req, HttpServletResponse resp, String account) {
        if (System.getenv("DB_URL") == null) {
            req.getSession(true).setAttribute("lastAccount", account);
            return;
        }
        resp.addHeader("Set-Cookie", NAME + "=" + account + "; Path=" + req.getContextPath()
            + "; HttpOnly; SameSite=Lax" + ("true".equals(System.getenv("COOKIE_SECURE")) ? "; Secure" : ""));
    }
}
