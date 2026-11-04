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
    /// Key prefix every new object is written under (e.g. `tenants/<id>/` for an
    /// ephemeral tenant whose IAM role is scoped to that prefix). Empty = none.
    pub s3_key_prefix: String,
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
            s3_key_prefix: normalize_key_prefix(&env::var("S3_KEY_PREFIX").unwrap_or_default()),
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

/// `tenants/acme` / `/tenants/acme/` -> `tenants/acme/`; empty, `.` and `..`
/// segments are dropped so the prefix can only ever narrow the key space.
pub fn normalize_key_prefix(raw: &str) -> String {
    let segments: Vec<&str> = raw
        .split('/')
        .filter(|s| !s.is_empty() && *s != "." && *s != "..")
        .collect();
    if segments.is_empty() {
        String::new()
    } else {
        format!("{}/", segments.join("/"))
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
mod key_prefix_tests {
    use super::normalize_key_prefix;

    #[test]
    fn empty_prefix_stays_empty() {
        assert_eq!(normalize_key_prefix(""), "");
        assert_eq!(normalize_key_prefix("/"), "");
    }

    #[test]
    fn prefix_gets_single_trailing_slash() {
        assert_eq!(normalize_key_prefix("tenants/acme"), "tenants/acme/");
        assert_eq!(normalize_key_prefix("/tenants//acme/"), "tenants/acme/");
    }

    #[test]
    fn traversal_segments_are_dropped() {
        assert_eq!(normalize_key_prefix("tenants/../acme/./"), "tenants/acme/");
        assert_eq!(normalize_key_prefix(".."), "");
    }
}
