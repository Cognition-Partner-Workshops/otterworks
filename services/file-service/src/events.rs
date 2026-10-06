use chrono::Utc;
use serde::Serialize;
use uuid::Uuid;

use crate::config::SnsConfig;
use crate::errors::ServiceError;

/// Publisher for file-service domain events via SNS.
#[derive(Clone)]
pub struct EventPublisher {
    client: aws_sdk_sns::Client,
    topic_arn: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FileEvent {
    pub event_type: String,
    pub file_id: String,
    pub owner_id: String,
    pub folder_id: Option<String>,
    #[serde(rename = "sharedWithUserId")]
    pub shared_with: Option<String>,
    pub timestamp: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mime_type: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub size_bytes: Option<u64>,
}

impl EventPublisher {
    pub async fn new(sns_config: &SnsConfig, aws: &crate::config::AwsConfig) -> Self {
        let sdk_config = aws.sdk_config_loader().load().await;
        Self::from_sdk_config(&sdk_config, sns_config.topic_arn.clone())
    }

    pub fn from_sdk_config(sdk_config: &aws_config::SdkConfig, topic_arn: Option<String>) -> Self {
        if topic_arn.is_none() {
            tracing::warn!(
                "SNS_TOPIC_ARN not set: file events will not be published \
                 (counted as file_service_events_total{{outcome=\"skipped_no_topic\"}})"
            );
        }
        Self {
            client: aws_sdk_sns::Client::new(sdk_config),
            topic_arn,
        }
    }

    /// Best-effort publish after the mutation has committed. Failures are not
    /// returned to the caller (the write already succeeded and a retry would
    /// duplicate it); instead they are counted and the full event is logged so
    /// it can be captured and re-published.
    async fn publish(&self, event: &FileEvent) {
        let outcome = match self.try_publish(event).await {
            Ok(true) => "published",
            Ok(false) => {
                tracing::debug!(event_type = %event.event_type, "SNS topic not configured, event not published");
                "skipped_no_topic"
            }
            Err(e) => {
                tracing::error!(
                    event_type = %event.event_type,
                    file_id = %event.file_id,
                    error = %e,
                    event = %serde_json::to_string(event).unwrap_or_default(),
                    "Failed to publish file event to SNS; event not delivered"
                );
                "failed"
            }
        };
        crate::middleware::FILE_EVENTS_TOTAL
            .with_label_values(&[&event.event_type, outcome])
            .inc();
    }

    async fn try_publish(&self, event: &FileEvent) -> Result<bool, ServiceError> {
        let topic_arn = match &self.topic_arn {
            Some(arn) => arn,
            None => return Ok(false),
        };

        let message =
            serde_json::to_string(event).map_err(|e| ServiceError::Internal(e.to_string()))?;

        let mut req = self.client.publish().topic_arn(topic_arn).message(&message);

        // message_group_id and message_deduplication_id are only valid for FIFO topics
        if topic_arn.ends_with(".fifo") {
            let dedup_id = format!("{}_{}", event.file_id, event.timestamp);
            req = req
                .message_group_id(&event.event_type)
                .message_deduplication_id(&dedup_id);
        }

        req.send()
            .await
            .map_err(|e| ServiceError::SnsError(e.to_string()))?;

        tracing::info!(
            event_type = %event.event_type,
            file_id = %event.file_id,
            "Published event to SNS"
        );
        Ok(true)
    }

    pub async fn file_uploaded(
        &self,
        file_id: &Uuid,
        owner_id: &Uuid,
        folder_id: Option<&Uuid>,
        name: &str,
        mime_type: &str,
        size_bytes: u64,
    ) {
        let event = FileEvent {
            event_type: "file_uploaded".into(),
            file_id: file_id.to_string(),
            owner_id: owner_id.to_string(),
            folder_id: folder_id.map(|f| f.to_string()),
            shared_with: None,
            timestamp: Utc::now().to_rfc3339(),
            name: Some(name.to_string()),
            mime_type: Some(mime_type.to_string()),
            size_bytes: Some(size_bytes),
        };
        self.publish(&event).await;
    }

    pub async fn file_deleted(&self, file_id: &Uuid, owner_id: &Uuid) {
        let event = FileEvent {
            event_type: "file_deleted".into(),
            file_id: file_id.to_string(),
            owner_id: owner_id.to_string(),
            folder_id: None,
            shared_with: None,
            timestamp: Utc::now().to_rfc3339(),
            name: None,
            mime_type: None,
            size_bytes: None,
        };
        self.publish(&event).await;
    }

    pub async fn file_shared(&self, file_id: &Uuid, owner_id: &Uuid, shared_with: &Uuid) {
        let event = FileEvent {
            event_type: "file_shared".into(),
            file_id: file_id.to_string(),
            owner_id: owner_id.to_string(),
            folder_id: None,
            shared_with: Some(shared_with.to_string()),
            timestamp: Utc::now().to_rfc3339(),
            name: None,
            mime_type: None,
            size_bytes: None,
        };
        self.publish(&event).await;
    }

    pub async fn file_trashed(&self, file_id: &Uuid, owner_id: &Uuid) {
        let event = FileEvent {
            event_type: "file_trashed".into(),
            file_id: file_id.to_string(),
            owner_id: owner_id.to_string(),
            folder_id: None,
            shared_with: None,
            timestamp: Utc::now().to_rfc3339(),
            name: None,
            mime_type: None,
            size_bytes: None,
        };
        self.publish(&event).await;
    }

    pub async fn file_restored(
        &self,
        file_id: &Uuid,
        owner_id: &Uuid,
        folder_id: Option<&Uuid>,
        name: &str,
        mime_type: &str,
        size_bytes: u64,
    ) {
        let event = FileEvent {
            event_type: "file_restored".into(),
            file_id: file_id.to_string(),
            owner_id: owner_id.to_string(),
            folder_id: folder_id.map(|f| f.to_string()),
            shared_with: None,
            timestamp: Utc::now().to_rfc3339(),
            name: Some(name.to_string()),
            mime_type: Some(mime_type.to_string()),
            size_bytes: Some(size_bytes),
        };
        self.publish(&event).await;
    }

    pub async fn file_updated(
        &self,
        file_id: &Uuid,
        owner_id: &Uuid,
        folder_id: Option<&Uuid>,
        name: &str,
        mime_type: &str,
        size_bytes: u64,
    ) {
        let event = FileEvent {
            event_type: "file_updated".into(),
            file_id: file_id.to_string(),
            owner_id: owner_id.to_string(),
            folder_id: folder_id.map(|f| f.to_string()),
            shared_with: None,
            timestamp: Utc::now().to_rfc3339(),
            name: Some(name.to_string()),
            mime_type: Some(mime_type.to_string()),
            size_bytes: Some(size_bytes),
        };
        self.publish(&event).await;
    }

    pub async fn file_moved(&self, file_id: &Uuid, owner_id: &Uuid, folder_id: Option<&Uuid>) {
        let event = FileEvent {
            event_type: "file_moved".into(),
            file_id: file_id.to_string(),
            owner_id: owner_id.to_string(),
            folder_id: folder_id.map(|f| f.to_string()),
            shared_with: None,
            timestamp: Utc::now().to_rfc3339(),
            name: None,
            mime_type: None,
            size_bytes: None,
        };
        self.publish(&event).await;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::test_support::*;
    use aws_smithy_http_client::test_util::NeverClient;
    use aws_smithy_runtime_api::shared::IntoShared;
    use std::time::{Duration, Instant};

    const TOPIC: &str = "arn:aws:sns:us-east-1:000000000000:test-file-events";

    #[tokio::test]
    async fn publish_failure_is_counted_not_silently_dropped() {
        let cfg = test_aws_config();
        let (http, calls) = fake_aws(|c| {
            if c.is("sns", "Publish") {
                sns_denied()
            } else {
                ddb_ok()
            }
        });
        let publisher =
            EventPublisher::from_sdk_config(&sdk_config(&cfg, http).await, Some(TOPIC.into()));
        let before = events_count("file_trashed", "failed");

        publisher
            .file_trashed(&Uuid::new_v4(), &Uuid::new_v4())
            .await;

        assert_eq!(events_count("file_trashed", "failed"), before + 1);
        // AuthorizationError is not retryable: exactly one attempt.
        assert_eq!(calls.lock().unwrap().len(), 1);
    }

    #[tokio::test]
    async fn publish_success_is_counted() {
        let cfg = test_aws_config();
        let (http, calls) = fake_aws(|_| sns_ok());
        let publisher =
            EventPublisher::from_sdk_config(&sdk_config(&cfg, http).await, Some(TOPIC.into()));
        let before = events_count("file_moved", "published");

        publisher
            .file_moved(&Uuid::new_v4(), &Uuid::new_v4(), None)
            .await;

        assert_eq!(events_count("file_moved", "published"), before + 1);
        let calls = calls.lock().unwrap();
        assert_eq!(calls.len(), 1);
        assert!(calls[0].body.contains("TopicArn="));
    }

    #[tokio::test]
    async fn missing_topic_is_counted_as_skipped() {
        let cfg = test_aws_config();
        let (http, calls) = fake_aws(|_| sns_ok());
        let publisher = EventPublisher::from_sdk_config(&sdk_config(&cfg, http).await, None);
        let before = events_count("file_restored", "skipped_no_topic");

        publisher
            .file_restored(
                &Uuid::new_v4(),
                &Uuid::new_v4(),
                None,
                "a.txt",
                "text/plain",
                1,
            )
            .await;

        assert_eq!(
            events_count("file_restored", "skipped_no_topic"),
            before + 1
        );
        assert!(calls.lock().unwrap().is_empty());
    }

    #[tokio::test]
    async fn sdk_defaults_never_time_out_a_hung_call() {
        // Characterises the pre-fix behaviour: the SDK sets no attempt or
        // operation timeout, so a hung SNS endpoint blocks indefinitely.
        let never = NeverClient::new();
        let sdk = aws_config::defaults(aws_config::BehaviorVersion::latest())
            .region(aws_config::Region::new("us-east-1"))
            .http_client(never.clone())
            .credentials_provider(aws_sdk_sns::config::Credentials::new(
                "test-akid",
                "test-secret",
                None,
                None,
                "test",
            ))
            .load()
            .await;
        let client = aws_sdk_sns::Client::new(&sdk);
        let res = tokio::time::timeout(
            Duration::from_secs(2),
            client.publish().topic_arn(TOPIC).message("{}").send(),
        )
        .await;
        assert!(res.is_err(), "call should still be pending after 2s");
    }

    #[tokio::test]
    async fn configured_deadlines_bound_a_hung_sns_call() {
        let cfg = test_aws_config();
        let never = NeverClient::new();
        let publisher = EventPublisher::from_sdk_config(
            &sdk_config(&cfg, never.clone().into_shared()).await,
            Some(TOPIC.into()),
        );
        let before = events_count("file_deleted", "failed");
        let started = Instant::now();

        tokio::time::timeout(
            Duration::from_secs(5),
            publisher.file_deleted(&Uuid::new_v4(), &Uuid::new_v4()),
        )
        .await
        .expect("publish must give up within the operation timeout");

        assert!(started.elapsed() < Duration::from_secs(2));
        assert_eq!(events_count("file_deleted", "failed"), before + 1);
        // Attempt timeouts are retried, bounded by max_attempts.
        let n = never.num_calls();
        assert!(
            (1..=cfg.tuning.max_attempts as usize).contains(&n),
            "calls = {n}"
        );
    }

    #[test]
    fn test_file_event_serialization() {
        let event = FileEvent {
            event_type: "file_uploaded".into(),
            file_id: Uuid::new_v4().to_string(),
            owner_id: Uuid::new_v4().to_string(),
            folder_id: None,
            shared_with: None,
            timestamp: Utc::now().to_rfc3339(),
            name: Some("test.txt".to_string()),
            mime_type: Some("text/plain".to_string()),
            size_bytes: Some(100),
        };
        let json = serde_json::to_string(&event).unwrap();
        assert!(json.contains("file_uploaded"));
        assert!(json.contains("eventType"));
        assert!(json.contains("fileId"));
        assert!(json.contains("ownerId"));
    }

    #[test]
    fn test_file_event_with_folder() {
        let folder = Uuid::new_v4();
        let event = FileEvent {
            event_type: "file_moved".into(),
            file_id: Uuid::new_v4().to_string(),
            owner_id: Uuid::new_v4().to_string(),
            folder_id: Some(folder.to_string()),
            shared_with: None,
            timestamp: Utc::now().to_rfc3339(),
            name: None,
            mime_type: None,
            size_bytes: None,
        };
        let json = serde_json::to_string(&event).unwrap();
        assert!(json.contains(&folder.to_string()));
        assert!(json.contains("folderId"));
    }
}
