use std::env;
use std::time::Duration;

use aws_config::retry::RetryConfig;
use aws_config::timeout::TimeoutConfig;

#[derive(Clone, Debug)]
pub struct AppConfig {
    pub server: ServerConfig,
    pub aws: AwsConfig,
    pub sns: SnsConfig,
}

#[derive(Clone, Debug)]
pub struct ServerConfig {
    pub port: u16,
    pub max_upload_bytes: u64,
}

#[derive(Clone, Debug)]
pub struct AwsConfig {
    pub region: String,
    pub endpoint_url: Option<String>,
    pub s3_bucket: String,
    pub dynamodb_table: String,
    pub dynamodb_folders_table: String,
    pub dynamodb_versions_table: String,
    pub dynamodb_shares_table: String,
    pub tuning: AwsClientTuning,
}

/// Request deadlines and retry bounds for the AWS SDK clients. The SDK has no
/// default attempt or operation timeout, so a stalled S3/DynamoDB/SNS call would
/// otherwise hold the request until the api-gateway's 30s write timeout fires.
/// Defaults keep a worst-case upload (S3 + two DynamoDB writes) under 30s.
#[derive(Clone, Debug, PartialEq)]
pub struct AwsClientTuning {
    pub connect_timeout: Duration,
    pub api_attempt_timeout: Duration,
    pub api_operation_timeout: Duration,
    pub s3_attempt_timeout: Duration,
    pub s3_operation_timeout: Duration,
    pub max_attempts: u32,
}

impl Default for AwsClientTuning {
    fn default() -> Self {
        Self {
            connect_timeout: Duration::from_millis(3_000),
            api_attempt_timeout: Duration::from_millis(1_500),
            api_operation_timeout: Duration::from_millis(4_000),
            s3_attempt_timeout: Duration::from_millis(15_000),
            s3_operation_timeout: Duration::from_millis(20_000),
            max_attempts: 3,
        }
    }
}

impl AwsClientTuning {
    pub fn from_lookup(lookup: impl Fn(&str) -> Option<String>) -> Self {
        let d = Self::default();
        let ms = |key: &str, default: Duration| {
            lookup(key)
                .and_then(|v| v.trim().parse::<u64>().ok())
                .filter(|v| *v > 0)
                .map(Duration::from_millis)
                .unwrap_or(default)
        };
        Self {
            connect_timeout: ms("AWS_CONNECT_TIMEOUT_MS", d.connect_timeout),
            api_attempt_timeout: ms("AWS_API_ATTEMPT_TIMEOUT_MS", d.api_attempt_timeout),
            api_operation_timeout: ms("AWS_API_OPERATION_TIMEOUT_MS", d.api_operation_timeout),
            s3_attempt_timeout: ms("S3_ATTEMPT_TIMEOUT_MS", d.s3_attempt_timeout),
            s3_operation_timeout: ms("S3_OPERATION_TIMEOUT_MS", d.s3_operation_timeout),
            max_attempts: lookup("AWS_MAX_ATTEMPTS")
                .and_then(|v| v.trim().parse::<u32>().ok())
                .filter(|v| (1..=10).contains(v))
                .unwrap_or(d.max_attempts),
        }
    }
}

#[derive(Clone, Debug)]
pub struct SnsConfig {
    pub topic_arn: Option<String>,
}

impl AppConfig {
    pub fn from_env() -> Self {
        Self {
            server: ServerConfig::from_env(),
            aws: AwsConfig::from_env(),
            sns: SnsConfig::from_env(),
        }
    }
}

impl ServerConfig {
    pub fn from_env() -> Self {
        Self {
            port: env::var("PORT")
                .unwrap_or_else(|_| "8082".into())
                .parse()
                .unwrap_or(8082),
            max_upload_bytes: env::var("MAX_UPLOAD_BYTES")
                .unwrap_or_else(|_| "104857600".into()) // 100 MB
                .parse()
                .unwrap_or(104_857_600),
        }
    }
}

impl AwsConfig {
    pub fn from_env() -> Self {
        Self {
            region: env::var("AWS_REGION").unwrap_or_else(|_| "us-east-1".into()),
            endpoint_url: env::var("AWS_ENDPOINT_URL").ok(),
            s3_bucket: env::var("S3_BUCKET").unwrap_or_else(|_| "otterworks-files".into()),
            dynamodb_table: env::var("DYNAMODB_TABLE")
                .unwrap_or_else(|_| "otterworks-file-metadata".into()),
            dynamodb_folders_table: env::var("DYNAMODB_FOLDERS_TABLE")
                .unwrap_or_else(|_| "otterworks-folders".into()),
            dynamodb_versions_table: env::var("DYNAMODB_VERSIONS_TABLE")
                .unwrap_or_else(|_| "otterworks-file-versions".into()),
            dynamodb_shares_table: env::var("DYNAMODB_SHARES_TABLE")
                .unwrap_or_else(|_| "otterworks-file-shares".into()),
            tuning: AwsClientTuning::from_lookup(|k| env::var(k).ok()),
        }
    }

    pub fn retry_config(&self) -> RetryConfig {
        RetryConfig::standard().with_max_attempts(self.tuning.max_attempts)
    }

    /// Deadlines for DynamoDB and SNS calls.
    pub fn api_timeout_config(&self) -> TimeoutConfig {
        TimeoutConfig::builder()
            .connect_timeout(self.tuning.connect_timeout)
            .operation_attempt_timeout(self.tuning.api_attempt_timeout)
            .operation_timeout(self.tuning.api_operation_timeout)
            .build()
    }

    /// Deadlines for S3 object calls, which carry up to MAX_UPLOAD_BYTES.
    pub fn s3_timeout_config(&self) -> TimeoutConfig {
        TimeoutConfig::builder()
            .connect_timeout(self.tuning.connect_timeout)
            .operation_attempt_timeout(self.tuning.s3_attempt_timeout)
            .operation_timeout(self.tuning.s3_operation_timeout)
            .build()
    }

    /// Shared SDK config loader with region, endpoint, deadlines and bounded retries.
    pub fn sdk_config_loader(&self) -> aws_config::ConfigLoader {
        let mut loader = aws_config::defaults(aws_config::BehaviorVersion::latest())
            .region(aws_config::Region::new(self.region.clone()))
            .retry_config(self.retry_config())
            .timeout_config(self.api_timeout_config());
        if let Some(endpoint) = &self.endpoint_url {
            loader = loader.endpoint_url(endpoint);
        }
        loader
    }
}

impl SnsConfig {
    pub fn from_env() -> Self {
        Self {
            topic_arn: env::var("SNS_TOPIC_ARN").ok(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tuning_defaults_bound_every_call() {
        let t = AwsClientTuning::from_lookup(|_| None);
        assert_eq!(t, AwsClientTuning::default());
        assert!(t.api_attempt_timeout < t.api_operation_timeout);
        assert!(t.s3_attempt_timeout < t.s3_operation_timeout);
        // S3 upload + version put + file put must fit inside the gateway's 30s write timeout.
        assert!(t.s3_operation_timeout + t.api_operation_timeout * 2 < Duration::from_secs(30));
        assert_eq!(t.max_attempts, 3);
    }

    #[test]
    fn tuning_reads_overrides_and_rejects_invalid_values() {
        let t = AwsClientTuning::from_lookup(|k| match k {
            "AWS_API_ATTEMPT_TIMEOUT_MS" => Some("250".into()),
            "S3_OPERATION_TIMEOUT_MS" => Some("0".into()),
            "AWS_MAX_ATTEMPTS" => Some("50".into()),
            "AWS_CONNECT_TIMEOUT_MS" => Some("abc".into()),
            _ => None,
        });
        let d = AwsClientTuning::default();
        assert_eq!(t.api_attempt_timeout, Duration::from_millis(250));
        assert_eq!(t.s3_operation_timeout, d.s3_operation_timeout);
        assert_eq!(t.max_attempts, d.max_attempts);
        assert_eq!(t.connect_timeout, d.connect_timeout);
    }

    #[test]
    fn timeout_configs_set_attempt_and_operation_deadlines() {
        let mut cfg = AwsConfig::from_env();
        cfg.tuning = AwsClientTuning::default();
        let api = cfg.api_timeout_config();
        assert_eq!(
            api.operation_attempt_timeout(),
            Some(cfg.tuning.api_attempt_timeout)
        );
        assert_eq!(
            api.operation_timeout(),
            Some(cfg.tuning.api_operation_timeout)
        );
        assert_eq!(api.connect_timeout(), Some(cfg.tuning.connect_timeout));
        let s3 = cfg.s3_timeout_config();
        assert_eq!(
            s3.operation_timeout(),
            Some(cfg.tuning.s3_operation_timeout)
        );
        assert_eq!(cfg.retry_config().max_attempts(), 3);
    }
}
