package example.claimshub.maps;

/**
 * Writes elements the way Saxon 12 serialised the goldens ({@code method="xml"}, no declaration, no
 * indentation): an element with no content is self-closed, text escapes {@code & < >} and carriage return.
 */
final class SaxonXmlWriter {

    private final StringBuilder out = new StringBuilder();

    SaxonXmlWriter raw(String markup) {
        out.append(markup);
        return this;
    }

    SaxonXmlWriter element(String name, String text) {
        if (text == null || text.isEmpty()) {
            out.append('<').append(name).append("/>");
        } else {
            out.append('<').append(name).append('>');
            escape(text);
            out.append("</").append(name).append('>');
        }
        return this;
    }

    private void escape(String text) {
        for (int i = 0; i < text.length(); i++) {
            char ch = text.charAt(i);
            switch (ch) {
                case '&' -> out.append("&amp;");
                case '<' -> out.append("&lt;");
                case '>' -> out.append("&gt;");
                case '\r' -> out.append("&#xD;");
                default -> out.append(ch);
            }
        }
    }

    @Override
    public String toString() {
        return out.toString();
    }
}
