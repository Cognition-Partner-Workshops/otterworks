package com.otterworks.report.ubw;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.stereotype.Component;

import javax.sql.DataSource;
import java.security.KeyFactory;
import java.security.PrivateKey;
import java.security.spec.PKCS8EncodedKeySpec;
import java.util.Base64;
import java.util.Locale;
import java.util.Properties;
import java.util.regex.Pattern;

/**
 * Connections to the warehouse selected by UBW_BACKEND. They are built here rather than exposed as
 * beans so the service's own PostgreSQL DataSource stays the auto-configured primary one.
 *
 * Snowflake logs in with key-pair auth as the run's service user; the database, warehouse and role
 * follow the run token naming of migration/snowflake/ESTATE.md (OW_UBW_&lt;TOKEN&gt;...).
 */
@Component
public class UbwDataSources {

    private static final Pattern RUN = Pattern.compile("^sfm-\\d{8}-[a-z0-9]{2,8}$");

    private final UbwBackend backend;
    private final String sqlServerUrl;
    private final String sqlServerUser;
    private final String sqlServerPassword;
    private final String snowflakeAccount;
    private final String snowflakeHost;
    private final String snowflakeRun;
    private final String snowflakeUser;
    private final String snowflakeRole;
    private final String snowflakePrivateKey;
    private volatile DataSource dataSource;

    public UbwDataSources(
            @Value("${ubw.backend:sqlserver}") String backend,
            @Value("${ubw.sqlserver.url:}") String sqlServerUrl,
            @Value("${ubw.sqlserver.user:}") String sqlServerUser,
            @Value("${ubw.sqlserver.password:}") String sqlServerPassword,
            @Value("${ubw.snowflake.account:}") String snowflakeAccount,
            @Value("${ubw.snowflake.host:}") String snowflakeHost,
            @Value("${ubw.snowflake.run:}") String snowflakeRun,
            @Value("${ubw.snowflake.user:}") String snowflakeUser,
            @Value("${ubw.snowflake.role:}") String snowflakeRole,
            @Value("${ubw.snowflake.private-key:}") String snowflakePrivateKey) {
        this.backend = UbwBackend.parse(backend);
        this.sqlServerUrl = sqlServerUrl;
        this.sqlServerUser = sqlServerUser;
        this.sqlServerPassword = sqlServerPassword;
        this.snowflakeAccount = snowflakeAccount;
        this.snowflakeHost = snowflakeHost;
        this.snowflakeRun = snowflakeRun;
        this.snowflakeUser = snowflakeUser;
        this.snowflakeRole = snowflakeRole;
        this.snowflakePrivateKey = snowflakePrivateKey;
    }

    public UbwBackend backend() {
        return backend;
    }

    public DataSource dataSource() {
        DataSource current = dataSource;
        if (current == null) {
            synchronized (this) {
                if (dataSource == null) {
                    dataSource = backend == UbwBackend.SNOWFLAKE ? snowflake() : sqlServer();
                }
                current = dataSource;
            }
        }
        return current;
    }

    private DataSource sqlServer() {
        require(sqlServerUrl, "UBW_SQL_URL (or UBW_SQL_HOST)");
        DriverManagerDataSource source = new DriverManagerDataSource(sqlServerUrl, sqlServerUser, sqlServerPassword);
        source.setDriverClassName("com.microsoft.sqlserver.jdbc.SQLServerDriver");
        return source;
    }

    private DataSource snowflake() {
        require(snowflakeRun, "UBW_RUN");
        require(snowflakePrivateKey, "SNOWFLAKE_PRIVATE_KEY");
        String prefix = prefix(snowflakeRun);
        String host = snowflakeHost.isEmpty()
                ? require(snowflakeAccount, "SNOWFLAKE_ACCOUNT") + ".snowflakecomputing.com"
                : snowflakeHost;
        String role = snowflakeRole.isEmpty() ? prefix + "_ENGINEER" : snowflakeRole;
        String url = "jdbc:snowflake://" + host + "/?db=" + prefix + "&warehouse=" + prefix + "_WH"
                + "&role=" + role + "&schema=REPORTS";
        Properties properties = new Properties();
        properties.put("user", snowflakeUser.isEmpty() ? prefix + "_DBT" : snowflakeUser);
        properties.put("privateKey", privateKey(snowflakePrivateKey));
        // JSON results avoid the Arrow reader's reflective access on newer JDKs.
        properties.put("JDBC_QUERY_RESULT_FORMAT", "JSON");
        if (!snowflakeAccount.isEmpty()) {
            properties.put("account", snowflakeAccount);
        }
        DriverManagerDataSource source = new DriverManagerDataSource(url);
        source.setDriverClassName("net.snowflake.client.jdbc.SnowflakeDriver");
        source.setConnectionProperties(properties);
        return source;
    }

    static String prefix(String run) {
        if (!RUN.matcher(run).matches()) {
            throw new IllegalStateException("UBW_RUN " + run + " does not look like sfm-<yyyymmdd>-<suffix>");
        }
        return "OW_UBW_" + run.toUpperCase(Locale.ROOT).replace('-', '_');
    }

    static PrivateKey privateKey(String pem) {
        String body = pem.replaceAll("-----(BEGIN|END) PRIVATE KEY-----", "").replaceAll("\\s", "");
        try {
            byte[] der = Base64.getDecoder().decode(body);
            return KeyFactory.getInstance("RSA").generatePrivate(new PKCS8EncodedKeySpec(der));
        } catch (Exception e) {
            throw new IllegalStateException("SNOWFLAKE_PRIVATE_KEY is not an unencrypted PKCS#8 RSA key", e);
        }
    }

    private static String require(String value, String name) {
        if (value == null || value.isEmpty()) {
            throw new IllegalStateException(name + " is not set for the UBW reports");
        }
        return value;
    }
}
