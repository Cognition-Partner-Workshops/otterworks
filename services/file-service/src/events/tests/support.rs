use super::EventPublisher;

impl EventPublisher {
    pub(crate) fn disabled_for_tests() -> Self {
        let config = aws_sdk_sns::config::Builder::new()
            .behavior_version_latest()
            .region(aws_sdk_sns::config::Region::new("us-east-1"))
            .build();
        Self {
            client: aws_sdk_sns::Client::from_conf(config),
            topic_arn: None,
        }
    }
}
