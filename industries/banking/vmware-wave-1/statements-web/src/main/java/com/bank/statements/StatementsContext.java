package com.bank.statements;

import javax.servlet.ServletContext;
import javax.servlet.ServletContextEvent;
import javax.servlet.ServletContextListener;
import org.apache.log4j.Logger;
import org.apache.tomcat.jdbc.pool.DataSource;

/** Builds the configuration and the connection pool once per web application. */
public class StatementsContext implements ServletContextListener {
    private static final Logger LOG = Logger.getLogger(StatementsContext.class);
    private static final String CONFIG = AppConfig.class.getName();
    private static final String DAO = StatementDao.class.getName();
    private static final String POOL = DataSource.class.getName();

    @Override
    public void contextInitialized(ServletContextEvent sce) {
        AppConfig config = AppConfig.fromEnv();
        DataSource pool = Database.create(config);
        ServletContext ctx = sce.getServletContext();
        ctx.setAttribute(CONFIG, config);
        ctx.setAttribute(POOL, pool);
        ctx.setAttribute(DAO, new StatementDao(pool));
        LOG.info("statements-web started bank=" + config.bankName() + " pageSize=" + config.pageSize());
    }

    @Override
    public void contextDestroyed(ServletContextEvent sce) {
        Object pool = sce.getServletContext().getAttribute(POOL);
        if (pool instanceof DataSource) {
            ((DataSource) pool).close();
        }
    }

    static AppConfig config(ServletContext ctx) {
        return (AppConfig) ctx.getAttribute(CONFIG);
    }

    static DataSource pool(ServletContext ctx) {
        return (DataSource) ctx.getAttribute(POOL);
    }

    static StatementDao dao(ServletContext ctx) {
        return (StatementDao) ctx.getAttribute(DAO);
    }
}
