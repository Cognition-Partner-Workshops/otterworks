import math
from pyspark.sql.functions import col, udf
from pyspark.sql.types import DoubleType
from common.runtime import landing, save, session


@udf(DoubleType())
def score(status, customer_id):
    linear = -1.8 + 0.04 * (customer_id % 50) + (1.2 if status == "closed" else 0.0)
    return 1.0 / (1.0 + math.exp(-linear))


spark = session("billing_churn_score")
result = landing(spark, "SUBSCRIPTION").withColumn("CHURN_SCORE", score(col("STATUS"), col("CUSTOMER_ID")))
save(result, "billing", "billing_churn_score")
spark.stop()
