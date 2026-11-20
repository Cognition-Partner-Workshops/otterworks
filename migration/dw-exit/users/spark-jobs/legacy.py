"""Execute unmodified legacy job bodies, adapting only local input/output."""
import os
from pathlib import Path
import runpy
import subprocess
import sys

from pyspark.sql import SparkSession

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
WORK = Path(os.environ['USERS_PARITY_WORK'])
sys.path.insert(0, str(ROOT / 'etl/spark/jobs/py'))
from common import runtime


def main():
    import pyspark
    jars = Path(pyspark.__file__).parent / 'jars'
    classes = WORK / 'classes'
    classes.mkdir(exist_ok=True)
    sources = ROOT / 'etl/spark/scala/src/main/scala/sfx'
    subprocess.run(['java', '-cp', str(jars / '*'), 'scala.tools.nsc.Main',
                    '-classpath', str(jars / '*'), '-d', str(classes),
                    str(HERE / 'LegacySupport.scala'), str(sources / 'TeamGraphComponents.scala'),
                    str(sources / 'UsersRiskScore.scala')], check=True)
    jar = WORK / 'legacy.jar'
    subprocess.run(['jar', 'cf', str(jar), '-C', str(classes), '.'], check=True)
    spark = (SparkSession.builder.master('local[2]').appName('users-parity-legacy')
             .config('spark.jars', str(jar)).config('spark.sql.shuffle.partitions', '4')
             .config('spark.ui.enabled', 'false').getOrCreate())
    runtime.session = lambda name: spark
    runtime.landing = lambda session, table: session.read.parquet(str(WORK / 'inputs' / table))
    runtime.save = lambda frame, area, name, *args: frame.write.mode('overwrite').parquet(
        str(WORK / 'legacy' / name))
    stop = spark.stop
    spark.stop = lambda: None
    selected = os.environ['USERS_PARITY_JOBS'].split(',')
    for name in ('user_pref_json_flatten', 'users_login_useragent_parse',
                 'users_active_daily', 'users_team_rollup'):
        if name not in selected:
            continue
        runpy.run_path(str(ROOT / 'etl/spark/jobs/py' / (name + '.py')))
    args = spark.sparkContext._gateway.new_array(spark._jvm.java.lang.String, 0)
    if 'team_graph_components' in selected:
        spark._jvm.sfx.TeamGraphComponents.main(args)
    if 'users_risk_score' in selected:
        spark._jvm.sfx.UsersRiskScore.main(args)
    stop()


if __name__ == '__main__':
    main()
