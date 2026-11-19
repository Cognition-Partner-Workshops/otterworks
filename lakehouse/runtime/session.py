import os

from delta import configure_spark_with_delta_pip
from pyspark.sql import SparkSession

from .layout import data_root, initialize


def create_session():
    root = data_root()
    root.mkdir(parents=True, exist_ok=True)
    builder = (SparkSession.builder.appName('otterworks-lakehouse')
               .master('local[2]')
               .config('spark.jars.repositories', os.environ.get(
                   'LAKEHOUSE_MAVEN_REPOSITORY', 'https://maven-central.storage-download.googleapis.com/maven2'))
               .config('spark.sql.extensions', 'io.delta.sql.DeltaSparkSessionExtension')
               .config('spark.sql.catalog.spark_catalog', 'org.apache.spark.sql.delta.catalog.DeltaCatalog')
               .config('spark.sql.warehouse.dir', str(root / 'warehouse'))
               .config('spark.hadoop.javax.jdo.option.ConnectionURL',
                       f'jdbc:derby:;databaseName={root / "metastore"};create=true')
               .config('spark.driver.extraJavaOptions', f'-Dderby.stream.error.file={root / "derby.log"}')
               .config('spark.sql.session.timeZone', 'UTC')
               .config('spark.sql.ansi.enabled', 'true')
               .config('spark.sql.shuffle.partitions', '2')
               .config('spark.databricks.delta.snapshotPartitions', '2')
               .enableHiveSupport())
    spark = configure_spark_with_delta_pip(builder).getOrCreate()
    spark.sparkContext.setLogLevel('ERROR')
    initialize(spark)
    return spark
