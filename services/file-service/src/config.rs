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
            s3_bucket: env::var("S3_BUCKET")
                .map(|v| v.trim().to_string())
                .unwrap_or_else(|_| "otterworks-files".into()),
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

impl AwsConfig {
    /// Reject configuration that can never work against S3 before we try to
    /// use it. Catches the empty / whitespace / templating-leftover cases that
    /// a bad Helm `--set` or env file produces.
    pub fn validate(&self) -> Result<(), String> {
        validate_bucket_name(&self.s3_bucket).map_err(|e| format!("S3_BUCKET {e}"))
    }
}

/// General-purpose S3 bucket naming rules (3-63 chars, lowercase letters,
/// digits, dots and hyphens, must start and end alphanumeric).
pub fn validate_bucket_name(name: &str) -> Result<(), String> {
    if name.is_empty() {
        return Err("must not be empty".into());
    }
    if !(3..=63).contains(&name.len()) {
        return Err(format!("'{name}' must be 3-63 characters long"));
    }
    if !name
        .chars()
        .all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == '-' || c == '.')
    {
        return Err(format!(
            "'{name}' may only contain lowercase letters, digits, '-' and '.'"
        ));
    }
    let first = name.chars().next().unwrap();
    let last = name.chars().last().unwrap();
    if !first.is_ascii_alphanumeric() || !last.is_ascii_alphanumeric() {
        return Err(format!(
            "'{name}' must start and end with a letter or digit"
        ));
    }
    Ok(())
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

    fn aws_config_with_bucket(bucket: &str) -> AwsConfig {
        AwsConfig {
            region: "us-east-1".into(),
            endpoint_url: None,
            s3_bucket: bucket.into(),
            dynamodb_table: "t".into(),
            dynamodb_folders_table: "f".into(),
            dynamodb_versions_table: "v".into(),
            dynamodb_shares_table: "s".into(),
        }
    }

    #[test]
    fn accepts_terraform_style_bucket_names() {
        for name in ["otterworks-files", "otterworks-files-dev", "my.bucket.1"] {
            assert!(validate_bucket_name(name).is_ok(), "{name}");
        }
    }

    #[test]
    fn rejects_empty_and_malformed_bucket_names() {
        for name in [
            "",
            "ab",
            "Otterworks-Files",
            "-leading",
            "trailing-",
            "has space",
            "${S3_BUCKET}",
        ] {
            assert!(validate_bucket_name(name).is_err(), "{name}");
        }
    }

    #[test]
    fn aws_config_validate_names_the_env_var() {
        let err = aws_config_with_bucket("").validate().unwrap_err();
        assert!(err.starts_with("S3_BUCKET"), "{err}");
        assert!(aws_config_with_bucket("otterworks-files")
            .validate()
            .is_ok());
    }
}
