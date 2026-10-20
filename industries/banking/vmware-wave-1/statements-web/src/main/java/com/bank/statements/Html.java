package com.bank.statements;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

public final class Html {
    private Html() {
    }

    public static String esc(String s) {
        if (s == null) {
            return "";
        }
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;");
    }

    static String page(String bank, String title, String body) {
        return "<!DOCTYPE html><html><head><meta charset=\"utf-8\"><title>" + esc(title) + " - " + esc(bank)
            + "</title><style>body{font-family:Arial,sans-serif;margin:2em;color:#1b2a3a}"
            + "table{border-collapse:collapse}td,th{padding:4px 10px;border-bottom:1px solid #ccd}"
            + "td.n{text-align:right}h1{color:#0b3d6b}</style></head><body><h1>" + esc(bank) + "</h1>"
            + "<h2>" + esc(title) + "</h2>" + body + "</body></html>";
    }

    public static String accounts(String bank, Map<String, String> accounts, String lastAccount) {
        StringBuilder b = new StringBuilder();
        if (lastAccount != null) {
            b.append("<p id=\"last\">Last viewed: <a href=\"statement?account=").append(esc(lastAccount)).append("\">")
                .append(esc(lastAccount)).append("</a></p>");
        }
        b.append("<table id=\"accounts\"><tr><th>Account</th><th>Holder</th></tr>");
        for (Map.Entry<String, String> e : accounts.entrySet()) {
            b.append("<tr><td><a href=\"statement?account=").append(esc(e.getKey())).append("\">").append(esc(e.getKey()))
                .append("</a></td><td>").append(esc(e.getValue())).append("</td></tr>");
        }
        b.append("</table>");
        return page(bank, "Accounts", b.toString());
    }

    public static String statement(String bank, String account, List<StatementLine> lines) {
        StringBuilder b = new StringBuilder("<p><a href=\"accounts\">All accounts</a></p>");
        b.append("<table id=\"statement\"><tr><th>Date</th><th>Description</th><th>Amount</th><th>Balance</th></tr>");
        BigDecimal total = BigDecimal.ZERO;
        for (StatementLine l : lines) {
            total = total.add(l.amount);
            b.append("<tr><td>").append(l.booked).append("</td><td>").append(esc(l.description))
                .append("</td><td class=\"n\">").append(l.amount.toPlainString())
                .append("</td><td class=\"n\">").append(l.balance.toPlainString()).append("</td></tr>");
        }
        b.append("</table><p id=\"summary\">").append(lines.size()).append(" lines, net movement ")
            .append(total.toPlainString()).append("</p>");
        return page(bank, "Statement " + account, b.toString());
    }
}
