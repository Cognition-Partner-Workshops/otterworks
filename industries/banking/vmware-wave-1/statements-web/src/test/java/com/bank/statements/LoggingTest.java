package com.bank.statements;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import java.util.Enumeration;
import org.apache.log4j.Appender;
import org.apache.log4j.ConsoleAppender;
import org.apache.log4j.FileAppender;
import org.apache.log4j.Logger;
import org.junit.Test;

public class LoggingTest {
    @Test
    public void applicationLogsGoToConsoleWithoutFiles() throws Exception {
        Logger root = Logger.getRootLogger();
        Enumeration<?> appenders = root.getAllAppenders();
        assertTrue("a console appender must be configured", appenders.hasMoreElements());
        Appender appender = (Appender) appenders.nextElement();
        assertFalse(appender instanceof FileAppender);
        assertTrue(appender instanceof ConsoleAppender);
        assertEquals("System.out", ((ConsoleAppender) appender).getTarget());
        assertFalse("no additional file appenders", appenders.hasMoreElements());

        ByteArrayOutputStream output = new ByteArrayOutputStream();
        PrintStream original = System.out;
        ConsoleAppender console = (ConsoleAppender) appender;
        try {
            System.setOut(new PrintStream(output, true, "UTF-8"));
            console.activateOptions();
            Logger.getLogger(LoggingTest.class).info("synthetic runtime log");
            assertTrue(output.toString("UTF-8").contains("synthetic runtime log"));
        } finally {
            System.setOut(original);
            console.activateOptions();
        }
    }
}
