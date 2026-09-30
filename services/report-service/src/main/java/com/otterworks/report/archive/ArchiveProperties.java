package com.otterworks.report.archive;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.util.Properties;

/**
 * Archive read-path settings, bound from {@code archive.*} which in turn map the
 * {@code ARCHIVE_STORE}, {@code LDM_NAMESPACE}, {@code LDM_SOURCE_PROVIDER}, {@code DB2_*}, {@code PG_*},
 * {@code AZSQL_*} and {@code SNOWFLAKE_*} environment variables (see application.properties).
 */
@ConfigurationProperties(prefix = "archive")
public class ArchiveProperties {

    private String store = "";
    private String namespace = "";
    private String sourceProvider = "db2";
    private final Db2 db2 = new Db2();
    private final Pg pg = new Pg();
    private final Azsql azsql = new Azsql();
    private final Snowflake snowflake = new Snowflake();

    public String getStore() {
        return store;
    }

    public void setStore(String store) {
        this.store = store;
    }

    public String getNamespace() {
        return namespace;
    }

    public void setNamespace(String namespace) {
        this.namespace = namespace;
    }

    /** The migrated estate's source driver ({@code db2} | {@code oracle}), reported with each run. */
    public String getSourceProvider() {
        return sourceProvider;
    }

    public void setSourceProvider(String sourceProvider) {
        this.sourceProvider = sourceProvider;
    }

    public Db2 getDb2() {
        return db2;
    }

    public Pg getPg() {
        return pg;
    }

    public Azsql getAzsql() {
        return azsql;
    }

    public Snowflake getSnowflake() {
        return snowflake;
    }

    public ArchiveStoreType storeType() {
        return ArchiveStoreType.parse(store);
    }

    /** Db2 connection settings (DB2_HOST, DB2_PORT, DB2_DATABASE, DB2_USER, DB2_PASSWORD). */
    public static class Db2 {
        private String host = "";
        private String port = "50000";
        private String database = "";
        private String user = "";
        private String password = "";

        public String getHost() {
            return host;
        }

        public void setHost(String host) {
            this.host = host;
        }

        public String getPort() {
            return port;
        }

        public void setPort(String port) {
            this.port = port;
        }

        public String getDatabase() {
            return database;
        }

        public void setDatabase(String database) {
            this.database = database;
        }

        public String getUser() {
            return user;
        }

        public void setUser(String user) {
            this.user = user;
        }

        public String getPassword() {
            return password;
        }

        public void setPassword(String password) {
            this.password = password;
        }

        public boolean isComplete() {
            return !isBlank(host) && !isBlank(database) && !isBlank(user) && !isBlank(password);
        }

        public String jdbcUrl() {
            return "jdbc:db2://" + host + ":" + port + "/" + database;
        }
    }

    /**
     * PostgreSQL connection settings (PG_HOST, PG_PORT, PG_DATABASE, PG_USER, PG_PASSWORD, PG_SSLMODE):
     * the tenant's existing database, in which the migration job created the mig/stg/arch schemas.
     */
    public static class Pg {
        private String host = "";
        private String port = "5432";
        private String database = "";
        private String user = "";
        private String password = "";
        private String sslmode = "prefer";

        public String getHost() {
            return host;
        }

        public void setHost(String host) {
            this.host = host;
        }

        public String getPort() {
            return port;
        }

        public void setPort(String port) {
            this.port = port;
        }

        public String getDatabase() {
            return database;
        }

        public void setDatabase(String database) {
            this.database = database;
        }

        public String getUser() {
            return user;
        }

        public void setUser(String user) {
            this.user = user;
        }

        public String getPassword() {
            return password;
        }

        public void setPassword(String password) {
            this.password = password;
        }

        public String getSslmode() {
            return sslmode;
        }

        public void setSslmode(String sslmode) {
            this.sslmode = sslmode;
        }

        public boolean isComplete() {
            return !isBlank(host) && !isBlank(database) && !isBlank(user) && !isBlank(password);
        }

        public String jdbcUrl() {
            return "jdbc:postgresql://" + host + ":" + port + "/" + database
                    + "?sslmode=" + (isBlank(sslmode) ? "prefer" : sslmode.trim());
        }
    }

    /** Azure SQL connection settings (AZSQL_SERVER, AZSQL_DATABASE, AZSQL_AUTH, AZSQL_USER, AZSQL_PASSWORD). */
    public static class Azsql {
        private String server = "";
        private String database = "";
        private String auth = "sql";
        private String user = "";
        private String password = "";
        private String clientId = "";

        public String getServer() {
            return server;
        }

        public void setServer(String server) {
            this.server = server;
        }

        public String getDatabase() {
            return database;
        }

        public void setDatabase(String database) {
            this.database = database;
        }

        public String getAuth() {
            return auth;
        }

        public void setAuth(String auth) {
            this.auth = auth;
        }

        public String getUser() {
            return user;
        }

        public void setUser(String user) {
            this.user = user;
        }

        public String getPassword() {
            return password;
        }

        public void setPassword(String password) {
            this.password = password;
        }

        public String getClientId() {
            return clientId;
        }

        public void setClientId(String clientId) {
            this.clientId = clientId;
        }

        public boolean isManagedIdentity() {
            return "managed-identity".equalsIgnoreCase(auth) || "msi".equalsIgnoreCase(auth);
        }

        public boolean isComplete() {
            if (isBlank(server) || isBlank(database)) {
                return false;
            }
            return isManagedIdentity() || (!isBlank(user) && !isBlank(password));
        }

        public String jdbcUrl() {
            String host = server.contains(".") ? server : server + ".database.windows.net";
            StringBuilder url = new StringBuilder("jdbc:sqlserver://").append(host).append(":1433;")
                    .append("databaseName=").append(database).append(';')
                    .append("encrypt=true;trustServerCertificate=false;loginTimeout=30;");
            if (isManagedIdentity()) {
                url.append("authentication=ActiveDirectoryMSI;");
                if (!isBlank(clientId)) {
                    url.append("msiClientId=").append(clientId).append(';');
                }
            }
            return url.toString();
        }
    }

    /**
     * Snowflake connection settings (SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PAT, SNOWFLAKE_ROLE,
     * SNOWFLAKE_WAREHOUSE, SNOWFLAKE_DATABASE): the tenant database {@code OTTERWORKS_LDM_<TOKEN>} of a split
     * target, read with a programmatic access token. The token only ever travels as a connection property.
     */
    public static class Snowflake {
        static final String AUTHENTICATOR = "PROGRAMMATIC_ACCESS_TOKEN";

        private String account = "";
        private String user = "";
        private String token = "";
        private String role = "";
        private String warehouse = "";
        private String database = "";

        public String getAccount() {
            return account;
        }

        public void setAccount(String account) {
            this.account = account;
        }

        public String getUser() {
            return user;
        }

        public void setUser(String user) {
            this.user = user;
        }

        public String getToken() {
            return token;
        }

        public void setToken(String token) {
            this.token = token;
        }

        public String getRole() {
            return role;
        }

        public void setRole(String role) {
            this.role = role;
        }

        public String getWarehouse() {
            return warehouse;
        }

        public void setWarehouse(String warehouse) {
            this.warehouse = warehouse;
        }

        public String getDatabase() {
            return database;
        }

        public void setDatabase(String database) {
            this.database = database;
        }

        public boolean isComplete() {
            return !isBlank(account) && !isBlank(user) && !isBlank(token) && !isBlank(database);
        }

        /** {@code ORG-ACCOUNT} identifiers become {@code <org-account>.snowflakecomputing.com}. */
        public String jdbcUrl() {
            String host = account.trim();
            if (!host.contains(".")) {
                host = host.replace('_', '-') + ".snowflakecomputing.com";
            }
            return "jdbc:snowflake://" + host + "/";
        }

        /** Driver properties: PAT authentication plus the session's role, warehouse and database. */
        public Properties connectionProperties() {
            Properties props = new Properties();
            props.setProperty("user", user.trim());
            props.setProperty("authenticator", AUTHENTICATOR);
            props.setProperty("token", token.trim());
            props.setProperty("db", database.trim());
            if (!isBlank(role)) {
                props.setProperty("role", role.trim());
            }
            if (!isBlank(warehouse)) {
                props.setProperty("warehouse", warehouse.trim());
            }
            // JSON result sets: the Arrow reader needs --add-opens on JDK 16+, and the archive reads are small.
            props.setProperty("JDBC_QUERY_RESULT_FORMAT", "JSON");
            props.setProperty("application", "otterworks-report-service");
            return props;
        }
    }

    static boolean isBlank(String value) {
        return value == null || value.trim().isEmpty();
    }
}
