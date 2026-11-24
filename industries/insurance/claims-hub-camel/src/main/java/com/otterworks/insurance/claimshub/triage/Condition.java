package com.otterworks.insurance.claimshub.triage;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * A rule condition from the rules table: clauses joined by {@code and}, each one of
 * {@code Fact op literal} (op is ==, !=, &gt;, &gt;=, &lt;, &lt;=) or {@code Fact in (A,B,C)}.
 * Literals are {@code true}/{@code false}, a decimal number, or a single-quoted string.
 */
public final class Condition {

    private static final Pattern COMPARISON = Pattern.compile("^(\\w+)\\s*(==|!=|>=|<=|>|<)\\s*(.+)$");
    private static final Pattern MEMBERSHIP = Pattern.compile("^(\\w+)\\s+in\\s+\\((.*)\\)$");
    private static final Pattern NUMBER = Pattern.compile("^-?\\d+(\\.\\d+)?$");
    private static final Pattern STRING = Pattern.compile("^'([^']*)'$");

    private final String text;
    private final List<Clause> clauses;

    private Condition(String text, List<Clause> clauses) {
        this.text = text;
        this.clauses = List.copyOf(clauses);
    }

    public static Condition parse(String text) {
        if (text == null || text.isBlank()) {
            throw new IllegalArgumentException("empty condition");
        }
        List<Clause> clauses = new ArrayList<>();
        for (String part : text.trim().split("\\s+and\\s+")) {
            clauses.add(parseClause(part.trim(), text));
        }
        return new Condition(text, clauses);
    }

    public boolean test(Map<String, String> facts) {
        for (Clause clause : clauses) {
            if (!clause.test(facts)) {
                return false;
            }
        }
        return true;
    }

    public List<String> facts() {
        return clauses.stream().map(Clause::fact).distinct().toList();
    }

    @Override
    public String toString() {
        return text;
    }

    private static Clause parseClause(String clause, String condition) {
        Matcher in = MEMBERSHIP.matcher(clause);
        if (in.matches()) {
            List<String> members = Arrays.stream(in.group(2).split(",")).map(String::trim).toList();
            if (members.stream().anyMatch(String::isEmpty)) {
                throw new IllegalArgumentException("empty member in '" + clause + "' of '" + condition + "'");
            }
            return new Clause(in.group(1), Operator.IN, new Literal.Members(members));
        }
        Matcher cmp = COMPARISON.matcher(clause);
        if (!cmp.matches()) {
            throw new IllegalArgumentException("cannot parse '" + clause + "' of '" + condition + "'");
        }
        Operator op = Operator.of(cmp.group(2));
        Literal literal = parseLiteral(cmp.group(3).trim(), clause);
        if (!(literal instanceof Literal.Number) && op != Operator.EQ && op != Operator.NE) {
            throw new IllegalArgumentException("'" + op.symbol + "' needs a number in '" + clause + "'");
        }
        return new Clause(cmp.group(1), op, literal);
    }

    private static Literal parseLiteral(String value, String clause) {
        if (value.equals("true") || value.equals("false")) {
            return new Literal.Bool(Boolean.parseBoolean(value));
        }
        if (NUMBER.matcher(value).matches()) {
            return new Literal.Number(new BigDecimal(value));
        }
        Matcher s = STRING.matcher(value);
        if (s.matches()) {
            return new Literal.Text(s.group(1));
        }
        throw new IllegalArgumentException("unknown literal '" + value + "' in '" + clause + "'");
    }

    private enum Operator {
        EQ("=="), NE("!="), GT(">"), GE(">="), LT("<"), LE("<="), IN("in");

        private final String symbol;

        Operator(String symbol) {
            this.symbol = symbol;
        }

        static Operator of(String symbol) {
            for (Operator op : values()) {
                if (op.symbol.equals(symbol)) {
                    return op;
                }
            }
            throw new IllegalArgumentException(symbol);
        }
    }

    private sealed interface Literal {
        record Bool(boolean value) implements Literal { }

        record Number(BigDecimal value) implements Literal { }

        record Text(String value) implements Literal { }

        record Members(List<String> values) implements Literal { }
    }

    private record Clause(String fact, Operator op, Literal literal) {

        boolean test(Map<String, String> facts) {
            String actual = facts.get(fact);
            if (actual == null) {
                throw new IllegalArgumentException("fact '" + fact + "' is missing");
            }
            return switch (literal) {
                case Literal.Members m -> m.values().contains(actual);
                case Literal.Bool b -> equality(actual.equals("true") == b.value());
                case Literal.Text t -> equality(actual.equals(t.value()));
                case Literal.Number n -> compare(new BigDecimal(actual.trim()).compareTo(n.value()));
            };
        }

        private boolean equality(boolean equal) {
            return op == Operator.EQ ? equal : !equal;
        }

        private boolean compare(int c) {
            return switch (op) {
                case EQ -> c == 0;
                case NE -> c != 0;
                case GT -> c > 0;
                case GE -> c >= 0;
                case LT -> c < 0;
                case LE -> c <= 0;
                case IN -> throw new IllegalStateException();
            };
        }
    }
}
