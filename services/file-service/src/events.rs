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
    pub async fn new(sns_config: &SnsConfig, aws_config: &crate::config::AwsConfig) -> Self {
        let mut aws_cfg_builder = aws_config::defaults(aws_config::BehaviorVersion::latest())
            .region(aws_config::Region::new(aws_config.region.clone()));

        if let Some(endpoint) = &aws_config.endpoint_url {
            aws_cfg_builder = aws_cfg_builder.endpoint_url(endpoint);
        }

        let aws_cfg = aws_cfg_builder.load().await;
        let client = aws_sdk_sns::Client::new(&aws_cfg);

        Self {
            client,
            topic_arn: sns_config.topic_arn.clone(),
        }
    }

    async fn publish(&self, event: &FileEvent) -> Result<(), ServiceError> {
        let topic_arn = match &self.topic_arn {
            Some(arn) => arn,
            None => {
                tracing::debug!("SNS topic not configured, skipping event publish");
                return Ok(());
            }
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
        Ok(())
    }

    pub async fn file_uploaded(
        &self,
        file_id: &Uuid,
        owner_id: &Uuid,
        folder_id: Option<&Uuid>,
        name: &str,
        mime_type: &str,
        size_bytes: u64,
    ) -> Result<(), ServiceError> {
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
        self.publish(&event).await
    }

    pub async fn file_deleted(&self, file_id: &Uuid, owner_id: &Uuid) -> Result<(), ServiceError> {
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
        self.publish(&event).await
    }

    pub async fn file_shared(
        &self,
        file_id: &Uuid,
        owner_id: &Uuid,
        shared_with: &Uuid,
    ) -> Result<(), ServiceError> {
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
        self.publish(&event).await
    }

    pub async fn file_trashed(&self, file_id: &Uuid, owner_id: &Uuid) -> Result<(), ServiceError> {
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
        self.publish(&event).await
    }

    pub async fn file_restored(
        &self,
        file_id: &Uuid,
        owner_id: &Uuid,
        folder_id: Option<&Uuid>,
        name: &str,
        mime_type: &str,
        size_bytes: u64,
    ) -> Result<(), ServiceError> {
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
        self.publish(&event).await
    }

    pub async fn file_updated(
        &self,
        file_id: &Uuid,
        owner_id: &Uuid,
        folder_id: Option<&Uuid>,
        name: &str,
        mime_type: &str,
        size_bytes: u64,
    ) -> Result<(), ServiceError> {
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
        self.publish(&event).await
    }

    pub async fn file_moved(
        &self,
        file_id: &Uuid,
        owner_id: &Uuid,
        folder_id: Option<&Uuid>,
    ) -> Result<(), ServiceError> {
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
        self.publish(&event).await
    }
}

#[cfg(test)]
impl EventPublisher {
    pub fn from_client(client: aws_sdk_sns::Client, topic_arn: Option<String>) -> Self {
        Self { client, topic_arn }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::test_support::FakeAws;

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

    const TOPIC: &str = "arn:aws:sns:us-east-1:000000000000:file-events";
    const FIFO_TOPIC: &str = "arn:aws:sns:us-east-1:000000000000:file-events.fifo";
    const PUBLISH_OK: &str = r#"<PublishResponse xmlns="http://sns.amazonaws.com/doc/2010-03-31/"><PublishResult><MessageId>m-1</MessageId></PublishResult><ResponseMetadata><RequestId>r-1</RequestId></ResponseMetadata></PublishResponse>"#;

    fn publisher(fake: &FakeAws, topic: Option<&str>) -> EventPublisher {
        EventPublisher::from_client(fake.sns(), topic.map(String::from))
    }

    fn published_message(fake: &FakeAws) -> serde_json::Value {
        let reqs = fake.requests_for("Publish");
        assert_eq!(reqs.len(), 1, "expected exactly one Publish call");
        serde_json::from_str(&reqs[0].form()["Message"]).unwrap()
    }

    #[test]
    fn optional_fields_are_omitted_when_none() {
        let event = FileEvent {
            event_type: "file_deleted".into(),
            file_id: "f".into(),
            owner_id: "o".into(),
            folder_id: None,
            shared_with: None,
            timestamp: "t".into(),
            name: None,
            mime_type: None,
            size_bytes: None,
        };
        let value = serde_json::to_value(&event).unwrap();
        let obj = value.as_object().unwrap();
        assert!(!obj.contains_key("name"));
        assert!(!obj.contains_key("mimeType"));
        assert!(!obj.contains_key("sizeBytes"));
        // folder and shared-with are always present, as null
        assert_eq!(value["folderId"], serde_json::Value::Null);
        assert_eq!(value["sharedWithUserId"], serde_json::Value::Null);
    }

    #[actix_rt::test]
    async fn publish_is_skipped_without_topic() {
        let fake = FakeAws::new();
        let p = publisher(&fake, None);
        let id = Uuid::new_v4();
        p.file_deleted(&id, &id).await.unwrap();
        p.file_trashed(&id, &id).await.unwrap();
        p.file_shared(&id, &id, &id).await.unwrap();
        p.file_moved(&id, &id, None).await.unwrap();
        assert!(fake.requests().is_empty());
    }

    #[actix_rt::test]
    async fn publishes_to_standard_topic_without_fifo_attributes() {
        let fake = FakeAws::new();
        fake.respond("Publish", 200, PUBLISH_OK);
        let p = publisher(&fake, Some(TOPIC));
        let (file, owner) = (Uuid::new_v4(), Uuid::new_v4());
        p.file_deleted(&file, &owner).await.unwrap();

        let form = fake.requests_for("Publish")[0].form();
        assert_eq!(form["TopicArn"], TOPIC);
        assert!(!form.contains_key("MessageGroupId"));
        assert!(!form.contains_key("MessageDeduplicationId"));
        let msg = published_message(&fake);
        assert_eq!(msg["eventType"], "file_deleted");
        assert_eq!(msg["fileId"], file.to_string());
        assert_eq!(msg["ownerId"], owner.to_string());
    }

    #[actix_rt::test]
    async fn fifo_topic_sets_group_and_dedup_ids() {
        let fake = FakeAws::new();
        fake.respond("Publish", 200, PUBLISH_OK);
        let p = publisher(&fake, Some(FIFO_TOPIC));
        let (file, owner) = (Uuid::new_v4(), Uuid::new_v4());
        p.file_trashed(&file, &owner).await.unwrap();

        let form = fake.requests_for("Publish")[0].form();
        let msg: serde_json::Value = serde_json::from_str(&form["Message"]).unwrap();
        assert_eq!(form["MessageGroupId"], "file_trashed");
        assert_eq!(
            form["MessageDeduplicationId"],
            format!("{}_{}", file, msg["timestamp"].as_str().unwrap())
        );
    }

    #[actix_rt::test]
    async fn sns_failure_maps_to_sns_error() {
        let fake = FakeAws::new();
        fake.respond(
            "Publish",
            404,
            r#"<ErrorResponse><Error><Type>Sender</Type><Code>NotFound</Code><Message>Topic does not exist</Message></Error><RequestId>r</RequestId></ErrorResponse>"#,
        );
        let p = publisher(&fake, Some(TOPIC));
        let id = Uuid::new_v4();
        let err = p.file_deleted(&id, &id).await.unwrap_err();
        assert!(matches!(err, ServiceError::SnsError(_)), "{err:?}");
    }

    #[actix_rt::test]
    async fn file_uploaded_event_carries_file_details() {
        let fake = FakeAws::new();
        fake.respond("Publish", 200, PUBLISH_OK);
        let (file, owner, folder) = (Uuid::new_v4(), Uuid::new_v4(), Uuid::new_v4());
        publisher(&fake, Some(TOPIC))
            .file_uploaded(&file, &owner, Some(&folder), "a.txt", "text/plain", 12)
            .await
            .unwrap();
        let msg = published_message(&fake);
        assert_eq!(msg["eventType"], "file_uploaded");
        assert_eq!(msg["folderId"], folder.to_string());
        assert_eq!(msg["name"], "a.txt");
        assert_eq!(msg["mimeType"], "text/plain");
        assert_eq!(msg["sizeBytes"], 12);
        assert_eq!(msg["sharedWithUserId"], serde_json::Value::Null);
        assert!(chrono::DateTime::parse_from_rfc3339(msg["timestamp"].as_str().unwrap()).is_ok());
    }

    #[actix_rt::test]
    async fn file_shared_event_carries_recipient() {
        let fake = FakeAws::new();
        fake.respond("Publish", 200, PUBLISH_OK);
        let (file, owner, with) = (Uuid::new_v4(), Uuid::new_v4(), Uuid::new_v4());
        publisher(&fake, Some(TOPIC))
            .file_shared(&file, &owner, &with)
            .await
            .unwrap();
        let msg = published_message(&fake);
        assert_eq!(msg["eventType"], "file_shared");
        assert_eq!(msg["sharedWithUserId"], with.to_string());
        assert!(msg.get("name").is_none());
    }

    #[actix_rt::test]
    async fn file_restored_and_updated_events_carry_file_details() {
        for kind in ["file_restored", "file_updated"] {
            let fake = FakeAws::new();
            fake.respond("Publish", 200, PUBLISH_OK);
            let p = publisher(&fake, Some(TOPIC));
            let (file, owner) = (Uuid::new_v4(), Uuid::new_v4());
            if kind == "file_restored" {
                p.file_restored(&file, &owner, None, "b.png", "image/png", 99)
                    .await
                    .unwrap();
            } else {
                p.file_updated(&file, &owner, None, "b.png", "image/png", 99)
                    .await
                    .unwrap();
            }
            let msg = published_message(&fake);
            assert_eq!(msg["eventType"], kind);
            assert_eq!(msg["name"], "b.png");
            assert_eq!(msg["mimeType"], "image/png");
            assert_eq!(msg["sizeBytes"], 99);
            assert_eq!(msg["folderId"], serde_json::Value::Null);
        }
    }

    #[actix_rt::test]
    async fn file_moved_event_carries_target_folder() {
        let fake = FakeAws::new();
        fake.respond("Publish", 200, PUBLISH_OK);
        let (file, owner, folder) = (Uuid::new_v4(), Uuid::new_v4(), Uuid::new_v4());
        publisher(&fake, Some(TOPIC))
            .file_moved(&file, &owner, Some(&folder))
            .await
            .unwrap();
        let msg = published_message(&fake);
        assert_eq!(msg["eventType"], "file_moved");
        assert_eq!(msg["folderId"], folder.to_string());
        assert!(msg.get("sizeBytes").is_none());
    }
}
