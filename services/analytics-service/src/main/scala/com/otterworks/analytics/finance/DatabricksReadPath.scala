package com.otterworks.analytics.finance

import java.sql.{Connection, DriverManager}
import java.util.Properties

/** Live JDBC transport; the consumer migration supplies native queries. */
object DatabricksReadPath:
  def connect(): Connection =
    val host = sys.env("DATABRICKS_HOST").stripPrefix("https://").stripSuffix("/")
    val warehouse = sys.env("DATABRICKS_WAREHOUSE_ID")
    require(host.matches("[a-zA-Z0-9.-]+\\.databricks\\.com"), "Invalid workspace host")
    require(warehouse.matches("[a-f0-9]+"), "Invalid warehouse id")
    val properties = new Properties()
    properties.setProperty("UID", "token")
    properties.setProperty("PWD", sys.env("DATABRICKS_TOKEN"))
    DriverManager.getConnection(s"jdbc:databricks://$host:443/default;transportMode=http;ssl=1;AuthMech=3;httpPath=/sql/1.0/warehouses/$warehouse;ConnCatalog=cpw;ConnSchema=dbx_d1111_after", properties)

  def tagged(nativeSql: String): String =
    "/* run=dbx-d1111 act=consumers step=contract consumer=analytics-service */\n" + nativeSql
