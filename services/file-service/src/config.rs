use std::env;

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
        }
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
    use std::sync::Mutex;

    // Environment variables are process-global; serialise the tests that touch them.
    static ENV_LOCK: Mutex<()> = Mutex::new(());

    const VARS: &[&str] = &[
        "PORT",
        "MAX_UPLOAD_BYTES",
        "AWS_REGION",
        "AWS_ENDPOINT_URL",
        "S3_BUCKET",
        "DYNAMODB_TABLE",
        "DYNAMODB_FOLDERS_TABLE",
        "DYNAMODB_VERSIONS_TABLE",
        "DYNAMODB_SHARES_TABLE",
        "SNS_TOPIC_ARN",
    ];

    fn with_env<T>(vars: &[(&str, &str)], f: impl FnOnce() -> T) -> T {
        let _guard = ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let saved: Vec<_> = VARS.iter().map(|k| (*k, env::var(k).ok())).collect();
        for k in VARS {
            env::remove_var(k);
        }
        for (k, v) in vars {
            env::set_var(k, v);
        }
        let out = f();
        for (k, v) in saved {
            match v {
                Some(v) => env::set_var(k, v),
                None => env::remove_var(k),
            }
        }
        out
    }

    #[test]
    fn defaults_when_env_is_empty() {
        let cfg = with_env(&[], AppConfig::from_env);
        assert_eq!(cfg.server.port, 8082);
        assert_eq!(cfg.server.max_upload_bytes, 100 * 1024 * 1024);
        assert_eq!(cfg.aws.region, "us-east-1");
        assert!(cfg.aws.endpoint_url.is_none());
        assert_eq!(cfg.aws.s3_bucket, "otterworks-files");
        assert_eq!(cfg.aws.dynamodb_table, "otterworks-file-metadata");
        assert_eq!(cfg.aws.dynamodb_folders_table, "otterworks-folders");
        assert_eq!(cfg.aws.dynamodb_versions_table, "otterworks-file-versions");
        assert_eq!(cfg.aws.dynamodb_shares_table, "otterworks-file-shares");
        assert!(cfg.sns.topic_arn.is_none());
    }

    #[test]
    fn reads_overrides_from_env() {
        let cfg = with_env(
            &[
                ("PORT", "9000"),
                ("MAX_UPLOAD_BYTES", "1024"),
                ("AWS_REGION", "eu-west-1"),
                ("AWS_ENDPOINT_URL", "http://localstack:4566"),
                ("S3_BUCKET", "b"),
                ("DYNAMODB_TABLE", "t1"),
                ("DYNAMODB_FOLDERS_TABLE", "t2"),
                ("DYNAMODB_VERSIONS_TABLE", "t3"),
                ("DYNAMODB_SHARES_TABLE", "t4"),
                ("SNS_TOPIC_ARN", "arn:aws:sns:eu-west-1:1:topic"),
            ],
            AppConfig::from_env,
        );
        assert_eq!(cfg.server.port, 9000);
        assert_eq!(cfg.server.max_upload_bytes, 1024);
        assert_eq!(cfg.aws.region, "eu-west-1");
        assert_eq!(
            cfg.aws.endpoint_url.as_deref(),
            Some("http://localstack:4566")
        );
        assert_eq!(cfg.aws.s3_bucket, "b");
        assert_eq!(cfg.aws.dynamodb_table, "t1");
        assert_eq!(cfg.aws.dynamodb_folders_table, "t2");
        assert_eq!(cfg.aws.dynamodb_versions_table, "t3");
        assert_eq!(cfg.aws.dynamodb_shares_table, "t4");
        assert_eq!(
            cfg.sns.topic_arn.as_deref(),
            Some("arn:aws:sns:eu-west-1:1:topic")
        );
    }

    #[test]
    fn invalid_numbers_fall_back_to_defaults() {
        let cfg = with_env(
            &[("PORT", "not-a-port"), ("MAX_UPLOAD_BYTES", "-5")],
            ServerConfig::from_env,
        );
        assert_eq!(cfg.port, 8082);
        assert_eq!(cfg.max_upload_bytes, 104_857_600);
    }

    #[test]
    fn out_of_range_port_falls_back_to_default() {
        let cfg = with_env(&[("PORT", "70000")], ServerConfig::from_env);
        assert_eq!(cfg.port, 8082);
    }
}
