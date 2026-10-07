use aws_sdk_dynamodb::types::AttributeValue;
use chrono::Utc;
use uuid::Uuid;

use crate::config::AwsConfig;
use crate::errors::ServiceError;
use crate::models::{FileMetadata, FileShare, FileVersion, Folder, SharePermission};

/// Check if an AWS SDK error is a ConditionalCheckFailedException.
fn is_conditional_check_failed<E: std::fmt::Debug>(
    err: &aws_sdk_dynamodb::error::SdkError<E>,
) -> bool {
    matches!(err, aws_sdk_dynamodb::error::SdkError::ServiceError(se)
        if format!("{:?}", se.err()).contains("ConditionalCheckFailed"))
}

/// Client for DynamoDB metadata operations.
#[derive(Clone)]
pub struct MetadataClient {
    pub client: aws_sdk_dynamodb::Client,
    pub files_table: String,
    pub folders_table: String,
    pub versions_table: String,
    pub shares_table: String,
}

impl MetadataClient {
    pub async fn new(config: &AwsConfig) -> Self {
        let mut aws_config_builder = aws_config::defaults(aws_config::BehaviorVersion::latest())
            .region(aws_config::Region::new(config.region.clone()));

        if let Some(endpoint) = &config.endpoint_url {
            aws_config_builder = aws_config_builder.endpoint_url(endpoint);
        }

        let aws_config = aws_config_builder.load().await;
        let client = aws_sdk_dynamodb::Client::new(&aws_config);

        Self {
            client,
            files_table: config.dynamodb_table.clone(),
            folders_table: config.dynamodb_folders_table.clone(),
            versions_table: config.dynamodb_versions_table.clone(),
            shares_table: config.dynamodb_shares_table.clone(),
        }
    }

    // -- File Metadata --

    pub async fn put_file(&self, file: &FileMetadata) -> Result<(), ServiceError> {
        let mut item = std::collections::HashMap::new();
        item.insert("id".into(), AttributeValue::S(file.id.to_string()));
        item.insert("name".into(), AttributeValue::S(file.name.clone()));
        item.insert(
            "mime_type".into(),
            AttributeValue::S(file.mime_type.clone()),
        );
        item.insert(
            "size_bytes".into(),
            AttributeValue::N(file.size_bytes.to_string()),
        );
        item.insert("s3_key".into(), AttributeValue::S(file.s3_key.clone()));
        item.insert(
            "owner_id".into(),
            AttributeValue::S(file.owner_id.to_string()),
        );
        item.insert(
            "version".into(),
            AttributeValue::N(file.version.to_string()),
        );
        item.insert("is_trashed".into(), AttributeValue::Bool(file.is_trashed));
        item.insert(
            "created_at".into(),
            AttributeValue::S(file.created_at.to_rfc3339()),
        );
        item.insert(
            "updated_at".into(),
            AttributeValue::S(file.updated_at.to_rfc3339()),
        );

        if let Some(folder_id) = &file.folder_id {
            item.insert("folder_id".into(), AttributeValue::S(folder_id.to_string()));
        }

        self.client
            .put_item()
            .table_name(&self.files_table)
            .set_item(Some(item))
            .send()
            .await
            .map_err(|e| ServiceError::DynamoError(e.to_string()))?;

        Ok(())
    }

    pub async fn get_file(&self, file_id: &Uuid) -> Result<FileMetadata, ServiceError> {
        let result = self
            .client
            .get_item()
            .table_name(&self.files_table)
            .key("id", AttributeValue::S(file_id.to_string()))
            .send()
            .await
            .map_err(|e| ServiceError::DynamoError(e.to_string()))?;

        let item = result
            .item()
            .ok_or_else(|| ServiceError::FileNotFound(file_id.to_string()))?;

        parse_file_metadata(item)
    }

    pub async fn delete_file(&self, file_id: &Uuid) -> Result<(), ServiceError> {
        self.client
            .delete_item()
            .table_name(&self.files_table)
            .key("id", AttributeValue::S(file_id.to_string()))
            .send()
            .await
            .map_err(|e| ServiceError::DynamoError(e.to_string()))?;
        Ok(())
    }

    pub async fn trash_file(&self, file_id: &Uuid) -> Result<FileMetadata, ServiceError> {
        let now = Utc::now();
        self.client
            .update_item()
            .table_name(&self.files_table)
            .key("id", AttributeValue::S(file_id.to_string()))
            .update_expression("SET is_trashed = :t, updated_at = :u")
            .condition_expression("attribute_exists(id)")
            .expression_attribute_values(":t", AttributeValue::Bool(true))
            .expression_attribute_values(":u", AttributeValue::S(now.to_rfc3339()))
            .send()
            .await
            .map_err(|e| {
                if is_conditional_check_failed(&e) {
                    return ServiceError::FileNotFound(file_id.to_string());
                }
                ServiceError::DynamoError(e.to_string())
            })?;

        self.get_file(file_id).await
    }

    pub async fn restore_file(&self, file_id: &Uuid) -> Result<FileMetadata, ServiceError> {
        let now = Utc::now();
        self.client
            .update_item()
            .table_name(&self.files_table)
            .key("id", AttributeValue::S(file_id.to_string()))
            .update_expression("SET is_trashed = :t, updated_at = :u")
            .condition_expression("attribute_exists(id)")
            .expression_attribute_values(":t", AttributeValue::Bool(false))
            .expression_attribute_values(":u", AttributeValue::S(now.to_rfc3339()))
            .send()
            .await
            .map_err(|e| {
                if is_conditional_check_failed(&e) {
                    return ServiceError::FileNotFound(file_id.to_string());
                }
                ServiceError::DynamoError(e.to_string())
            })?;

        self.get_file(file_id).await
    }

    pub async fn rename_file(
        &self,
        file_id: &Uuid,
        name: &str,
    ) -> Result<FileMetadata, ServiceError> {
        let now = Utc::now();
        self.client
            .update_item()
            .table_name(&self.files_table)
            .key("id", AttributeValue::S(file_id.to_string()))
            .update_expression("SET #n = :n, updated_at = :u")
            .condition_expression("attribute_exists(id)")
            .expression_attribute_names("#n", "name")
            .expression_attribute_values(":n", AttributeValue::S(name.to_string()))
            .expression_attribute_values(":u", AttributeValue::S(now.to_rfc3339()))
            .send()
            .await
            .map_err(|e| {
                if is_conditional_check_failed(&e) {
                    return ServiceError::FileNotFound(file_id.to_string());
                }
                ServiceError::DynamoError(e.to_string())
            })?;

        self.get_file(file_id).await
    }

    pub async fn move_file(
        &self,
        file_id: &Uuid,
        folder_id: Option<Uuid>,
    ) -> Result<FileMetadata, ServiceError> {
        let now = Utc::now();
        let mut update_builder = self
            .client
            .update_item()
            .table_name(&self.files_table)
            .key("id", AttributeValue::S(file_id.to_string()))
            .condition_expression("attribute_exists(id)")
            .expression_attribute_values(":u", AttributeValue::S(now.to_rfc3339()));

        if let Some(fid) = &folder_id {
            update_builder = update_builder
                .update_expression("SET folder_id = :f, updated_at = :u")
                .expression_attribute_values(":f", AttributeValue::S(fid.to_string()));
        } else {
            update_builder =
                update_builder.update_expression("SET updated_at = :u REMOVE folder_id");
        }

        update_builder.send().await.map_err(|e| {
            if is_conditional_check_failed(&e) {
                return ServiceError::FileNotFound(file_id.to_string());
            }
            ServiceError::DynamoError(e.to_string())
        })?;

        self.get_file(file_id).await
    }

    pub async fn list_trashed(
        &self,
        owner_id: Option<Uuid>,
    ) -> Result<Vec<FileMetadata>, ServiceError> {
        let mut filter_parts = vec!["is_trashed = :trashed".to_string()];
        let mut scan_builder = self
            .client
            .scan()
            .table_name(&self.files_table)
            .expression_attribute_values(":trashed", AttributeValue::Bool(true));

        if let Some(oid) = &owner_id {
            filter_parts.push("owner_id = :owner_id".to_string());
            scan_builder = scan_builder
                .expression_attribute_values(":owner_id", AttributeValue::S(oid.to_string()));
        }

        scan_builder = scan_builder.filter_expression(filter_parts.join(" AND "));

        let mut paginator = scan_builder.into_paginator().send();
        let mut files = Vec::new();
        while let Some(page) = paginator.next().await {
            let page = page.map_err(|e| ServiceError::DynamoError(e.to_string()))?;
            if let Some(items) = page.items {
                for item in &items {
                    files.push(parse_file_metadata(item)?);
                }
            }
        }

        files.sort_by_key(|f| std::cmp::Reverse(f.updated_at));
        Ok(files)
    }

    pub async fn list_files(
        &self,
        folder_id: Option<Uuid>,
        owner_id: Option<Uuid>,
        include_trashed: bool,
    ) -> Result<Vec<FileMetadata>, ServiceError> {
        let mut scan_builder = self.client.scan().table_name(&self.files_table);

        let mut filter_parts: Vec<String> = Vec::new();

        if let Some(fid) = &folder_id {
            filter_parts.push("folder_id = :folder_id".to_string());
            scan_builder = scan_builder
                .expression_attribute_values(":folder_id", AttributeValue::S(fid.to_string()));
        }
        if let Some(oid) = &owner_id {
            filter_parts.push("owner_id = :owner_id".to_string());
            scan_builder = scan_builder
                .expression_attribute_values(":owner_id", AttributeValue::S(oid.to_string()));
        }
        if !include_trashed {
            filter_parts.push("is_trashed = :trashed".to_string());
            scan_builder =
                scan_builder.expression_attribute_values(":trashed", AttributeValue::Bool(false));
        }

        if !filter_parts.is_empty() {
            scan_builder = scan_builder.filter_expression(filter_parts.join(" AND "));
        }

        // Use the SDK paginator to handle DynamoDB's 1MB-per-Scan limit automatically
        let mut paginator = scan_builder.into_paginator().send();
        let mut files = Vec::new();
        while let Some(page) = paginator.next().await {
            let page = page.map_err(|e| ServiceError::DynamoError(e.to_string()))?;
            for item in page.items() {
                files.push(parse_file_metadata(item)?);
            }
        }
        Ok(files)
    }

    // -- Folder --

    pub async fn put_folder(&self, folder: &Folder) -> Result<(), ServiceError> {
        let mut item = std::collections::HashMap::new();
        item.insert("id".into(), AttributeValue::S(folder.id.to_string()));
        item.insert("name".into(), AttributeValue::S(folder.name.clone()));
        item.insert(
            "owner_id".into(),
            AttributeValue::S(folder.owner_id.to_string()),
        );
        item.insert(
            "created_at".into(),
            AttributeValue::S(folder.created_at.to_rfc3339()),
        );
        item.insert(
            "updated_at".into(),
            AttributeValue::S(folder.updated_at.to_rfc3339()),
        );

        if let Some(pid) = &folder.parent_id {
            item.insert("parent_id".into(), AttributeValue::S(pid.to_string()));
        }

        self.client
            .put_item()
            .table_name(&self.folders_table)
            .set_item(Some(item))
            .send()
            .await
            .map_err(|e| ServiceError::DynamoError(e.to_string()))?;

        Ok(())
    }

    pub async fn get_folder(&self, folder_id: &Uuid) -> Result<Folder, ServiceError> {
        let result = self
            .client
            .get_item()
            .table_name(&self.folders_table)
            .key("id", AttributeValue::S(folder_id.to_string()))
            .send()
            .await
            .map_err(|e| ServiceError::DynamoError(e.to_string()))?;

        let item = result
            .item()
            .ok_or_else(|| ServiceError::FolderNotFound(folder_id.to_string()))?;

        parse_folder(item)
    }

    pub async fn update_folder(
        &self,
        folder_id: &Uuid,
        name: Option<String>,
        parent_id: Option<Uuid>,
    ) -> Result<Folder, ServiceError> {
        let now = Utc::now();
        let mut update_parts = vec!["updated_at = :u".to_string()];
        let mut builder = self
            .client
            .update_item()
            .table_name(&self.folders_table)
            .key("id", AttributeValue::S(folder_id.to_string()))
            .condition_expression("attribute_exists(id)")
            .expression_attribute_values(":u", AttributeValue::S(now.to_rfc3339()));

        if let Some(n) = &name {
            update_parts.push("#n = :n".to_string());
            builder = builder
                .expression_attribute_names("#n", "name")
                .expression_attribute_values(":n", AttributeValue::S(n.clone()));
        }
        if let Some(pid) = &parent_id {
            update_parts.push("parent_id = :p".to_string());
            builder = builder.expression_attribute_values(":p", AttributeValue::S(pid.to_string()));
        }

        builder = builder.update_expression(format!("SET {}", update_parts.join(", ")));

        builder.send().await.map_err(|e| {
            if is_conditional_check_failed(&e) {
                return ServiceError::FolderNotFound(folder_id.to_string());
            }
            ServiceError::DynamoError(e.to_string())
        })?;

        self.get_folder(folder_id).await
    }

    pub async fn delete_folder(&self, folder_id: &Uuid) -> Result<(), ServiceError> {
        self.client
            .delete_item()
            .table_name(&self.folders_table)
            .key("id", AttributeValue::S(folder_id.to_string()))
            .send()
            .await
            .map_err(|e| ServiceError::DynamoError(e.to_string()))?;
        Ok(())
    }

    pub async fn list_folders(
        &self,
        parent_id: Option<Uuid>,
        owner_id: Option<Uuid>,
    ) -> Result<Vec<Folder>, ServiceError> {
        let mut scan_builder = self.client.scan().table_name(&self.folders_table);

        let mut filter_parts: Vec<String> = Vec::new();

        match &parent_id {
            Some(pid) => {
                filter_parts.push("parent_id = :parent_id".to_string());
                scan_builder = scan_builder
                    .expression_attribute_values(":parent_id", AttributeValue::S(pid.to_string()));
            }
            None => {
                filter_parts.push("attribute_not_exists(parent_id)".to_string());
            }
        }
        if let Some(oid) = &owner_id {
            filter_parts.push("owner_id = :owner_id".to_string());
            scan_builder = scan_builder
                .expression_attribute_values(":owner_id", AttributeValue::S(oid.to_string()));
        }

        if !filter_parts.is_empty() {
            scan_builder = scan_builder.filter_expression(filter_parts.join(" AND "));
        }

        let mut paginator = scan_builder.into_paginator().send();
        let mut folders = Vec::new();
        while let Some(page) = paginator.next().await {
            let page = page.map_err(|e| ServiceError::DynamoError(e.to_string()))?;
            for item in page.items() {
                folders.push(parse_folder(item)?);
            }
        }
        Ok(folders)
    }

    // -- File Versions --

    pub async fn put_version(&self, version: &FileVersion) -> Result<(), ServiceError> {
        let mut item = std::collections::HashMap::new();
        item.insert(
            "file_id".into(),
            AttributeValue::S(version.file_id.to_string()),
        );
        item.insert(
            "version".into(),
            AttributeValue::N(version.version.to_string()),
        );
        item.insert("s3_key".into(), AttributeValue::S(version.s3_key.clone()));
        item.insert(
            "size_bytes".into(),
            AttributeValue::N(version.size_bytes.to_string()),
        );
        item.insert(
            "created_by".into(),
            AttributeValue::S(version.created_by.to_string()),
        );
        item.insert(
            "created_at".into(),
            AttributeValue::S(version.created_at.to_rfc3339()),
        );

        self.client
            .put_item()
            .table_name(&self.versions_table)
            .set_item(Some(item))
            .send()
            .await
            .map_err(|e| ServiceError::DynamoError(e.to_string()))?;

        Ok(())
    }

    pub async fn list_versions(&self, file_id: &Uuid) -> Result<Vec<FileVersion>, ServiceError> {
        let result = self
            .client
            .query()
            .table_name(&self.versions_table)
            .key_condition_expression("file_id = :fid")
            .expression_attribute_values(":fid", AttributeValue::S(file_id.to_string()))
            .scan_index_forward(false)
            .send()
            .await
            .map_err(|e| ServiceError::DynamoError(e.to_string()))?;

        let items = result.items();
        let mut versions = Vec::with_capacity(items.len());
        for item in items {
            versions.push(parse_file_version(item)?);
        }
        Ok(versions)
    }

    // -- File Shares --

    pub async fn put_share(&self, share: &FileShare) -> Result<(), ServiceError> {
        let mut item = std::collections::HashMap::new();
        item.insert("id".into(), AttributeValue::S(share.id.to_string()));
        item.insert(
            "file_id".into(),
            AttributeValue::S(share.file_id.to_string()),
        );
        item.insert(
            "shared_with".into(),
            AttributeValue::S(share.shared_with.to_string()),
        );
        item.insert(
            "permission".into(),
            AttributeValue::S(share.permission.to_string()),
        );
        item.insert(
            "shared_by".into(),
            AttributeValue::S(share.shared_by.to_string()),
        );
        item.insert(
            "created_at".into(),
            AttributeValue::S(share.created_at.to_rfc3339()),
        );

        self.client
            .put_item()
            .table_name(&self.shares_table)
            .set_item(Some(item))
            .send()
            .await
            .map_err(|e| ServiceError::DynamoError(e.to_string()))?;

        Ok(())
    }

    pub async fn find_existing_share(
        &self,
        file_id: &Uuid,
        shared_with: &Uuid,
    ) -> Result<Option<FileShare>, ServiceError> {
        let mut paginator = self
            .client
            .scan()
            .table_name(&self.shares_table)
            .filter_expression("file_id = :fid AND shared_with = :uid")
            .expression_attribute_values(":fid", AttributeValue::S(file_id.to_string()))
            .expression_attribute_values(":uid", AttributeValue::S(shared_with.to_string()))
            .into_paginator()
            .items()
            .send();

        if let Some(item) = paginator.next().await {
            let item = item.map_err(|e| ServiceError::DynamoError(e.to_string()))?;
            return Ok(Some(parse_file_share(&item)?));
        }
        Ok(None)
    }

    pub async fn list_shares_for_user(
        &self,
        user_id: &Uuid,
    ) -> Result<Vec<FileShare>, ServiceError> {
        let mut paginator = self
            .client
            .scan()
            .table_name(&self.shares_table)
            .filter_expression("shared_with = :uid")
            .expression_attribute_values(":uid", AttributeValue::S(user_id.to_string()))
            .into_paginator()
            .send();

        let mut shares = Vec::new();
        while let Some(page) = paginator.next().await {
            let page = page.map_err(|e| ServiceError::DynamoError(e.to_string()))?;
            if let Some(items) = page.items {
                for item in &items {
                    shares.push(parse_file_share(item)?);
                }
            }
        }
        Ok(shares)
    }

    pub async fn list_shares_by_owner(
        &self,
        owner_id: &Uuid,
    ) -> Result<Vec<FileShare>, ServiceError> {
        let mut paginator = self
            .client
            .scan()
            .table_name(&self.shares_table)
            .filter_expression("shared_by = :uid")
            .expression_attribute_values(":uid", AttributeValue::S(owner_id.to_string()))
            .into_paginator()
            .items()
            .send();

        let mut shares = Vec::new();
        while let Some(item) = paginator.next().await {
            let item = item.map_err(|e| ServiceError::DynamoError(e.to_string()))?;
            shares.push(parse_file_share(&item)?);
        }
        Ok(shares)
    }

    pub async fn delete_share(&self, share_id: &Uuid) -> Result<(), ServiceError> {
        self.client
            .delete_item()
            .table_name(&self.shares_table)
            .key("id", AttributeValue::S(share_id.to_string()))
            .send()
            .await
            .map_err(|e| ServiceError::DynamoError(e.to_string()))?;
        Ok(())
    }

    pub async fn list_shares(&self, file_id: &Uuid) -> Result<Vec<FileShare>, ServiceError> {
        let mut shares = Vec::new();
        let mut paginator = self
            .client
            .scan()
            .table_name(&self.shares_table)
            .filter_expression("file_id = :fid")
            .expression_attribute_values(":fid", AttributeValue::S(file_id.to_string()))
            .into_paginator()
            .items()
            .send();

        while let Some(item) = paginator.next().await {
            let item = item.map_err(|e| ServiceError::DynamoError(e.to_string()))?;
            shares.push(parse_file_share(&item)?);
        }
        Ok(shares)
    }
}

// -- Parsing helpers --

fn get_s(
    item: &std::collections::HashMap<String, AttributeValue>,
    key: &str,
) -> Result<String, ServiceError> {
    item.get(key)
        .and_then(|v| v.as_s().ok())
        .map(|s| s.to_string())
        .ok_or_else(|| ServiceError::DynamoError(format!("missing field: {key}")))
}

fn get_n_u64(
    item: &std::collections::HashMap<String, AttributeValue>,
    key: &str,
) -> Result<u64, ServiceError> {
    item.get(key)
        .and_then(|v| v.as_n().ok())
        .and_then(|n| n.parse::<u64>().ok())
        .ok_or_else(|| ServiceError::DynamoError(format!("missing numeric field: {key}")))
}

fn get_n_u32(
    item: &std::collections::HashMap<String, AttributeValue>,
    key: &str,
) -> Result<u32, ServiceError> {
    item.get(key)
        .and_then(|v| v.as_n().ok())
        .and_then(|n| n.parse::<u32>().ok())
        .ok_or_else(|| ServiceError::DynamoError(format!("missing numeric field: {key}")))
}

fn get_bool(
    item: &std::collections::HashMap<String, AttributeValue>,
    key: &str,
) -> Result<bool, ServiceError> {
    item.get(key)
        .and_then(|v| v.as_bool().ok())
        .copied()
        .ok_or_else(|| ServiceError::DynamoError(format!("missing bool field: {key}")))
}

fn get_optional_s(
    item: &std::collections::HashMap<String, AttributeValue>,
    key: &str,
) -> Option<String> {
    item.get(key)
        .and_then(|v| v.as_s().ok())
        .map(|s| s.to_string())
}

fn parse_uuid(s: &str) -> Result<uuid::Uuid, ServiceError> {
    s.parse::<uuid::Uuid>()
        .map_err(|e| ServiceError::DynamoError(format!("invalid UUID: {e}")))
}

fn parse_datetime(s: &str) -> Result<chrono::DateTime<chrono::Utc>, ServiceError> {
    chrono::DateTime::parse_from_rfc3339(s)
        .map(|dt| dt.with_timezone(&chrono::Utc))
        .map_err(|e| ServiceError::DynamoError(format!("invalid datetime: {e}")))
}

fn parse_file_metadata(
    item: &std::collections::HashMap<String, AttributeValue>,
) -> Result<FileMetadata, ServiceError> {
    Ok(FileMetadata {
        id: parse_uuid(&get_s(item, "id")?)?,
        name: get_s(item, "name")?,
        mime_type: get_s(item, "mime_type")?,
        size_bytes: get_n_u64(item, "size_bytes")?,
        s3_key: get_s(item, "s3_key")?,
        folder_id: get_optional_s(item, "folder_id")
            .as_deref()
            .map(parse_uuid)
            .transpose()?,
        owner_id: parse_uuid(&get_s(item, "owner_id")?)?,
        version: get_n_u32(item, "version")?,
        is_trashed: get_bool(item, "is_trashed")?,
        created_at: parse_datetime(&get_s(item, "created_at")?)?,
        updated_at: parse_datetime(&get_s(item, "updated_at")?)?,
    })
}

fn parse_folder(
    item: &std::collections::HashMap<String, AttributeValue>,
) -> Result<Folder, ServiceError> {
    Ok(Folder {
        id: parse_uuid(&get_s(item, "id")?)?,
        name: get_s(item, "name")?,
        parent_id: get_optional_s(item, "parent_id")
            .as_deref()
            .map(parse_uuid)
            .transpose()?,
        owner_id: parse_uuid(&get_s(item, "owner_id")?)?,
        created_at: parse_datetime(&get_s(item, "created_at")?)?,
        updated_at: parse_datetime(&get_s(item, "updated_at")?)?,
    })
}

fn parse_file_version(
    item: &std::collections::HashMap<String, AttributeValue>,
) -> Result<FileVersion, ServiceError> {
    Ok(FileVersion {
        file_id: parse_uuid(&get_s(item, "file_id")?)?,
        version: get_n_u32(item, "version")?,
        s3_key: get_s(item, "s3_key")?,
        size_bytes: get_n_u64(item, "size_bytes")?,
        created_by: parse_uuid(&get_s(item, "created_by")?)?,
        created_at: parse_datetime(&get_s(item, "created_at")?)?,
    })
}

fn parse_file_share(
    item: &std::collections::HashMap<String, AttributeValue>,
) -> Result<FileShare, ServiceError> {
    let permission_str = get_s(item, "permission")?;
    let permission = SharePermission::from_str_value(&permission_str).ok_or_else(|| {
        ServiceError::DynamoError(format!("invalid permission: {permission_str}"))
    })?;

    Ok(FileShare {
        id: parse_uuid(&get_s(item, "id")?)?,
        file_id: parse_uuid(&get_s(item, "file_id")?)?,
        shared_with: parse_uuid(&get_s(item, "shared_with")?)?,
        permission,
        shared_by: parse_uuid(&get_s(item, "shared_by")?)?,
        created_at: parse_datetime(&get_s(item, "created_at")?)?,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    fn make_file_item() -> HashMap<String, AttributeValue> {
        let now = Utc::now();
        let id = Uuid::new_v4();
        let owner = Uuid::new_v4();
        let mut item = HashMap::new();
        item.insert("id".into(), AttributeValue::S(id.to_string()));
        item.insert("name".into(), AttributeValue::S("test.txt".into()));
        item.insert("mime_type".into(), AttributeValue::S("text/plain".into()));
        item.insert("size_bytes".into(), AttributeValue::N("1024".into()));
        item.insert("s3_key".into(), AttributeValue::S(format!("files/{id}")));
        item.insert("owner_id".into(), AttributeValue::S(owner.to_string()));
        item.insert("version".into(), AttributeValue::N("1".into()));
        item.insert("is_trashed".into(), AttributeValue::Bool(false));
        item.insert("created_at".into(), AttributeValue::S(now.to_rfc3339()));
        item.insert("updated_at".into(), AttributeValue::S(now.to_rfc3339()));
        item
    }

    #[test]
    fn test_parse_file_metadata_success() {
        let item = make_file_item();
        let result = parse_file_metadata(&item);
        assert!(result.is_ok());
        let file = result.unwrap();
        assert_eq!(file.name, "test.txt");
        assert_eq!(file.mime_type, "text/plain");
        assert_eq!(file.size_bytes, 1024);
        assert_eq!(file.version, 1);
        assert!(!file.is_trashed);
        assert!(file.folder_id.is_none());
    }

    #[test]
    fn test_parse_file_metadata_with_folder() {
        let mut item = make_file_item();
        let folder_id = Uuid::new_v4();
        item.insert("folder_id".into(), AttributeValue::S(folder_id.to_string()));
        let file = parse_file_metadata(&item).unwrap();
        assert_eq!(file.folder_id, Some(folder_id));
    }

    #[test]
    fn test_parse_file_metadata_missing_field() {
        let mut item = make_file_item();
        item.remove("name");
        let result = parse_file_metadata(&item);
        assert!(result.is_err());
    }

    #[test]
    fn test_parse_folder() {
        let now = Utc::now();
        let id = Uuid::new_v4();
        let owner = Uuid::new_v4();
        let mut item = HashMap::new();
        item.insert("id".into(), AttributeValue::S(id.to_string()));
        item.insert("name".into(), AttributeValue::S("Documents".into()));
        item.insert("owner_id".into(), AttributeValue::S(owner.to_string()));
        item.insert("created_at".into(), AttributeValue::S(now.to_rfc3339()));
        item.insert("updated_at".into(), AttributeValue::S(now.to_rfc3339()));

        let folder = parse_folder(&item).unwrap();
        assert_eq!(folder.name, "Documents");
        assert_eq!(folder.id, id);
        assert!(folder.parent_id.is_none());
    }

    #[test]
    fn test_parse_file_version() {
        let now = Utc::now();
        let file_id = Uuid::new_v4();
        let user_id = Uuid::new_v4();
        let mut item = HashMap::new();
        item.insert("file_id".into(), AttributeValue::S(file_id.to_string()));
        item.insert("version".into(), AttributeValue::N("3".into()));
        item.insert("s3_key".into(), AttributeValue::S("files/v3/key".into()));
        item.insert("size_bytes".into(), AttributeValue::N("2048".into()));
        item.insert("created_by".into(), AttributeValue::S(user_id.to_string()));
        item.insert("created_at".into(), AttributeValue::S(now.to_rfc3339()));

        let ver = parse_file_version(&item).unwrap();
        assert_eq!(ver.file_id, file_id);
        assert_eq!(ver.version, 3);
        assert_eq!(ver.size_bytes, 2048);
    }

    #[test]
    fn test_parse_file_share() {
        let now = Utc::now();
        let share_id = Uuid::new_v4();
        let file_id = Uuid::new_v4();
        let user_a = Uuid::new_v4();
        let user_b = Uuid::new_v4();
        let mut item = HashMap::new();
        item.insert("id".into(), AttributeValue::S(share_id.to_string()));
        item.insert("file_id".into(), AttributeValue::S(file_id.to_string()));
        item.insert("shared_with".into(), AttributeValue::S(user_a.to_string()));
        item.insert("permission".into(), AttributeValue::S("editor".into()));
        item.insert("shared_by".into(), AttributeValue::S(user_b.to_string()));
        item.insert("created_at".into(), AttributeValue::S(now.to_rfc3339()));

        let share = parse_file_share(&item).unwrap();
        assert_eq!(share.permission, SharePermission::Editor);
        assert_eq!(share.file_id, file_id);
    }

    #[test]
    fn test_share_permission_from_str() {
        assert_eq!(
            SharePermission::from_str_value("viewer"),
            Some(SharePermission::Viewer)
        );
        assert_eq!(
            SharePermission::from_str_value("Editor"),
            Some(SharePermission::Editor)
        );
        assert_eq!(SharePermission::from_str_value("invalid"), None);
    }
}

#[cfg(test)]
mod parse_tests {
    use super::*;
    use std::collections::HashMap;

    fn item(pairs: &[(&str, AttributeValue)]) -> HashMap<String, AttributeValue> {
        pairs
            .iter()
            .map(|(k, v)| (k.to_string(), v.clone()))
            .collect()
    }

    fn assert_dynamo_err<T>(r: Result<T, ServiceError>, needle: &str) {
        match r {
            Err(ServiceError::DynamoError(msg)) => assert!(msg.contains(needle), "{msg}"),
            Err(e) => panic!("expected DynamoError containing {needle:?}, got {e}"),
            Ok(_) => panic!("expected DynamoError containing {needle:?}, got Ok"),
        }
    }

    #[test]
    fn get_s_rejects_missing_and_wrong_type() {
        let i = item(&[("n", AttributeValue::N("1".into()))]);
        assert_dynamo_err(get_s(&i, "n"), "missing field: n");
        assert_dynamo_err(get_s(&i, "absent"), "missing field: absent");
    }

    #[test]
    fn numeric_getters_validate_values() {
        let i = item(&[
            ("ok", AttributeValue::N("7".into())),
            ("neg", AttributeValue::N("-1".into())),
            ("big", AttributeValue::N("5000000000".into())),
            ("str", AttributeValue::S("7".into())),
        ]);
        assert_eq!(get_n_u64(&i, "ok").unwrap(), 7);
        assert_eq!(get_n_u32(&i, "ok").unwrap(), 7);
        assert_eq!(get_n_u64(&i, "big").unwrap(), 5_000_000_000);
        assert_dynamo_err(get_n_u32(&i, "big"), "missing numeric field: big");
        assert_dynamo_err(get_n_u64(&i, "neg"), "missing numeric field: neg");
        assert_dynamo_err(get_n_u64(&i, "str"), "missing numeric field: str");
        assert_dynamo_err(get_n_u32(&i, "absent"), "missing numeric field: absent");
    }

    #[test]
    fn get_bool_requires_bool_attribute() {
        let i = item(&[
            ("t", AttributeValue::Bool(true)),
            ("s", AttributeValue::S("true".into())),
        ]);
        assert!(get_bool(&i, "t").unwrap());
        assert_dynamo_err(get_bool(&i, "s"), "missing bool field: s");
    }

    #[test]
    fn get_optional_s_ignores_wrong_type() {
        let i = item(&[
            ("s", AttributeValue::S("v".into())),
            ("n", AttributeValue::N("1".into())),
        ]);
        assert_eq!(get_optional_s(&i, "s").as_deref(), Some("v"));
        assert_eq!(get_optional_s(&i, "n"), None);
        assert_eq!(get_optional_s(&i, "absent"), None);
    }

    #[test]
    fn parse_uuid_and_datetime_report_invalid_input() {
        assert_dynamo_err(parse_uuid("nope"), "invalid UUID");
        assert_dynamo_err(parse_datetime("yesterday"), "invalid datetime");
        let dt = parse_datetime("2024-03-01T10:00:00+02:00").unwrap();
        assert_eq!(dt.to_rfc3339(), "2024-03-01T08:00:00+00:00");
    }

    fn file_item() -> HashMap<String, AttributeValue> {
        item(&[
            ("id", AttributeValue::S(Uuid::new_v4().to_string())),
            ("name", AttributeValue::S("a".into())),
            ("mime_type", AttributeValue::S("text/plain".into())),
            ("size_bytes", AttributeValue::N("1".into())),
            ("s3_key", AttributeValue::S("k".into())),
            ("owner_id", AttributeValue::S(Uuid::new_v4().to_string())),
            ("version", AttributeValue::N("2".into())),
            ("is_trashed", AttributeValue::Bool(true)),
            (
                "created_at",
                AttributeValue::S("2024-01-01T00:00:00+00:00".into()),
            ),
            (
                "updated_at",
                AttributeValue::S("2024-01-02T00:00:00+00:00".into()),
            ),
        ])
    }

    #[test]
    fn parse_file_metadata_rejects_bad_folder_id() {
        let mut i = file_item();
        i.insert("folder_id".into(), AttributeValue::S("bad".into()));
        assert_dynamo_err(parse_file_metadata(&i), "invalid UUID");
    }

    #[test]
    fn parse_file_metadata_rejects_bad_owner_and_timestamps() {
        let mut i = file_item();
        i.insert("owner_id".into(), AttributeValue::S("bad".into()));
        assert_dynamo_err(parse_file_metadata(&i), "invalid UUID");

        let mut i = file_item();
        i.insert("updated_at".into(), AttributeValue::S("bad".into()));
        assert_dynamo_err(parse_file_metadata(&i), "invalid datetime");
    }

    #[test]
    fn parse_file_metadata_reads_trash_and_version() {
        let f = parse_file_metadata(&file_item()).unwrap();
        assert!(f.is_trashed);
        assert_eq!(f.version, 2);
    }

    #[test]
    fn parse_folder_reads_parent() {
        let parent = Uuid::new_v4();
        let i = item(&[
            ("id", AttributeValue::S(Uuid::new_v4().to_string())),
            ("name", AttributeValue::S("d".into())),
            ("parent_id", AttributeValue::S(parent.to_string())),
            ("owner_id", AttributeValue::S(Uuid::new_v4().to_string())),
            (
                "created_at",
                AttributeValue::S("2024-01-01T00:00:00+00:00".into()),
            ),
            (
                "updated_at",
                AttributeValue::S("2024-01-01T00:00:00+00:00".into()),
            ),
        ]);
        assert_eq!(parse_folder(&i).unwrap().parent_id, Some(parent));
    }

    #[test]
    fn parse_file_share_rejects_unknown_permission() {
        let i = item(&[
            ("id", AttributeValue::S(Uuid::new_v4().to_string())),
            ("permission", AttributeValue::S("owner".into())),
        ]);
        assert_dynamo_err(parse_file_share(&i), "invalid permission: owner");
    }

    #[test]
    fn parse_file_version_requires_created_by() {
        let i = item(&[
            ("file_id", AttributeValue::S(Uuid::new_v4().to_string())),
            ("version", AttributeValue::N("1".into())),
            ("s3_key", AttributeValue::S("k".into())),
            ("size_bytes", AttributeValue::N("1".into())),
        ]);
        assert_dynamo_err(parse_file_version(&i), "missing field: created_by");
    }
}

#[cfg(test)]
mod client_tests {
    use super::*;
    use crate::test_support::{
        file_item, folder_item, get_item_response, scan_response, share_item, ts, version_item,
        FakeAws,
    };
    use serde_json::json;

    const T1: &str = "2024-01-01T00:00:00+00:00";
    const T2: &str = "2024-02-01T00:00:00+00:00";
    const T3: &str = "2024-03-01T00:00:00+00:00";

    fn sample_file(folder_id: Option<Uuid>) -> FileMetadata {
        FileMetadata {
            id: Uuid::new_v4(),
            name: "a.txt".into(),
            mime_type: "text/plain".into(),
            size_bytes: 5,
            s3_key: "files/o/a".into(),
            folder_id,
            owner_id: Uuid::new_v4(),
            version: 1,
            is_trashed: false,
            created_at: ts(T1),
            updated_at: ts(T1),
        }
    }

    fn only(fake: &FakeAws, op: &str) -> serde_json::Value {
        let reqs = fake.requests_for(op);
        assert_eq!(reqs.len(), 1, "expected one {op} call, got {}", reqs.len());
        reqs[0].json()
    }

    fn expect_err<T: std::fmt::Debug>(r: Result<T, ServiceError>) -> ServiceError {
        r.expect_err("expected an error")
    }

    // -- files --

    #[actix_rt::test]
    async fn put_file_writes_all_attributes() {
        let fake = FakeAws::new();
        fake.respond_json("PutItem", json!({}));
        let folder = Uuid::new_v4();
        let file = sample_file(Some(folder));
        fake.metadata_client().put_file(&file).await.unwrap();

        let body = only(&fake, "PutItem");
        assert_eq!(body["TableName"], "files");
        let item = &body["Item"];
        assert_eq!(item["id"]["S"], file.id.to_string());
        assert_eq!(item["size_bytes"]["N"], "5");
        assert_eq!(item["version"]["N"], "1");
        assert_eq!(item["is_trashed"]["BOOL"], false);
        assert_eq!(item["folder_id"]["S"], folder.to_string());
        assert_eq!(item["created_at"]["S"], T1);
    }

    #[actix_rt::test]
    async fn put_file_omits_folder_when_none() {
        let fake = FakeAws::new();
        fake.respond_json("PutItem", json!({}));
        fake.metadata_client()
            .put_file(&sample_file(None))
            .await
            .unwrap();
        assert!(only(&fake, "PutItem")["Item"].get("folder_id").is_none());
    }

    #[actix_rt::test]
    async fn put_file_maps_sdk_failure() {
        let fake = FakeAws::new();
        fake.dynamo_error("PutItem", "ProvisionedThroughputExceededException");
        let err = expect_err(fake.metadata_client().put_file(&sample_file(None)).await);
        assert!(matches!(err, ServiceError::DynamoError(_)), "{err:?}");
    }

    #[actix_rt::test]
    async fn get_file_returns_parsed_item() {
        let fake = FakeAws::new();
        let (id, owner) = (Uuid::new_v4(), Uuid::new_v4());
        fake.respond_json(
            "GetItem",
            get_item_response(file_item(id, owner, "x.txt", T1, false)),
        );
        let file = fake.metadata_client().get_file(&id).await.unwrap();
        assert_eq!(file.id, id);
        assert_eq!(file.owner_id, owner);
        assert_eq!(file.name, "x.txt");
        let body = only(&fake, "GetItem");
        assert_eq!(body["TableName"], "files");
        assert_eq!(body["Key"]["id"]["S"], id.to_string());
    }

    #[actix_rt::test]
    async fn get_file_missing_item_is_not_found() {
        let fake = FakeAws::new();
        fake.respond_json("GetItem", json!({}));
        let id = Uuid::new_v4();
        let err = expect_err(fake.metadata_client().get_file(&id).await);
        assert!(matches!(err, ServiceError::FileNotFound(ref s) if *s == id.to_string()));
    }

    #[actix_rt::test]
    async fn get_file_sdk_failure_is_dynamo_error() {
        let fake = FakeAws::new();
        fake.dynamo_error("GetItem", "ResourceNotFoundException");
        let err = expect_err(fake.metadata_client().get_file(&Uuid::new_v4()).await);
        assert!(matches!(err, ServiceError::DynamoError(_)), "{err:?}");
    }

    #[actix_rt::test]
    async fn delete_file_deletes_by_id() {
        let fake = FakeAws::new();
        fake.respond_json("DeleteItem", json!({}));
        let id = Uuid::new_v4();
        fake.metadata_client().delete_file(&id).await.unwrap();
        let body = only(&fake, "DeleteItem");
        assert_eq!(body["TableName"], "files");
        assert_eq!(body["Key"]["id"]["S"], id.to_string());
    }

    #[actix_rt::test]
    async fn trash_and_restore_toggle_flag_and_reload() {
        for (trash, flag) in [(true, true), (false, false)] {
            let fake = FakeAws::new();
            let (id, owner) = (Uuid::new_v4(), Uuid::new_v4());
            fake.respond_json("UpdateItem", json!({}));
            fake.respond_json(
                "GetItem",
                get_item_response(file_item(id, owner, "a", T2, flag)),
            );
            let meta = fake.metadata_client();
            let file = if trash {
                meta.trash_file(&id).await.unwrap()
            } else {
                meta.restore_file(&id).await.unwrap()
            };
            assert_eq!(file.is_trashed, flag);

            let body = only(&fake, "UpdateItem");
            assert_eq!(body["Key"]["id"]["S"], id.to_string());
            assert_eq!(body["ConditionExpression"], "attribute_exists(id)");
            assert_eq!(
                body["UpdateExpression"],
                "SET is_trashed = :t, updated_at = :u"
            );
            assert_eq!(body["ExpressionAttributeValues"][":t"]["BOOL"], flag);
            assert_eq!(fake.requests_for("GetItem").len(), 1);
        }
    }

    #[actix_rt::test]
    async fn conditional_check_failure_maps_to_file_not_found() {
        let id = Uuid::new_v4();
        for op in ["trash", "restore", "rename", "move"] {
            let fake = FakeAws::new();
            fake.dynamo_error("UpdateItem", "ConditionalCheckFailedException");
            let meta = fake.metadata_client();
            let res = match op {
                "trash" => meta.trash_file(&id).await,
                "restore" => meta.restore_file(&id).await,
                "rename" => meta.rename_file(&id, "n").await,
                _ => meta.move_file(&id, None).await,
            };
            let err = expect_err(res);
            assert!(
                matches!(err, ServiceError::FileNotFound(ref s) if *s == id.to_string()),
                "{op}: {err:?}"
            );
            assert!(fake.requests_for("GetItem").is_empty(), "{op}");
        }
    }

    #[actix_rt::test]
    async fn other_update_failures_map_to_dynamo_error() {
        let id = Uuid::new_v4();
        for op in ["trash", "restore", "rename", "move"] {
            let fake = FakeAws::new();
            fake.dynamo_error("UpdateItem", "ProvisionedThroughputExceededException");
            let meta = fake.metadata_client();
            let res = match op {
                "trash" => meta.trash_file(&id).await,
                "restore" => meta.restore_file(&id).await,
                "rename" => meta.rename_file(&id, "n").await,
                _ => meta.move_file(&id, Some(id)).await,
            };
            let err = expect_err(res);
            assert!(matches!(err, ServiceError::DynamoError(_)), "{op}: {err:?}");
        }
    }

    #[actix_rt::test]
    async fn rename_file_sets_name_via_placeholder() {
        let fake = FakeAws::new();
        let (id, owner) = (Uuid::new_v4(), Uuid::new_v4());
        fake.respond_json("UpdateItem", json!({}));
        fake.respond_json(
            "GetItem",
            get_item_response(file_item(id, owner, "new.txt", T2, false)),
        );
        let file = fake
            .metadata_client()
            .rename_file(&id, "new.txt")
            .await
            .unwrap();
        assert_eq!(file.name, "new.txt");
        let body = only(&fake, "UpdateItem");
        assert_eq!(body["UpdateExpression"], "SET #n = :n, updated_at = :u");
        assert_eq!(body["ExpressionAttributeNames"]["#n"], "name");
        assert_eq!(body["ExpressionAttributeValues"][":n"]["S"], "new.txt");
    }

    #[actix_rt::test]
    async fn move_file_into_folder_sets_folder_id() {
        let fake = FakeAws::new();
        let (id, owner, folder) = (Uuid::new_v4(), Uuid::new_v4(), Uuid::new_v4());
        fake.respond_json("UpdateItem", json!({}));
        fake.respond_json(
            "GetItem",
            get_item_response(file_item(id, owner, "a", T2, false)),
        );
        fake.metadata_client()
            .move_file(&id, Some(folder))
            .await
            .unwrap();
        let body = only(&fake, "UpdateItem");
        assert_eq!(
            body["UpdateExpression"],
            "SET folder_id = :f, updated_at = :u"
        );
        assert_eq!(
            body["ExpressionAttributeValues"][":f"]["S"],
            folder.to_string()
        );
    }

    #[actix_rt::test]
    async fn move_file_to_root_removes_folder_id() {
        let fake = FakeAws::new();
        let (id, owner) = (Uuid::new_v4(), Uuid::new_v4());
        fake.respond_json("UpdateItem", json!({}));
        fake.respond_json(
            "GetItem",
            get_item_response(file_item(id, owner, "a", T2, false)),
        );
        fake.metadata_client().move_file(&id, None).await.unwrap();
        let body = only(&fake, "UpdateItem");
        assert_eq!(
            body["UpdateExpression"],
            "SET updated_at = :u REMOVE folder_id"
        );
        assert!(body["ExpressionAttributeValues"].get(":f").is_none());
    }

    #[actix_rt::test]
    async fn list_trashed_filters_by_owner_and_sorts_newest_first() {
        let fake = FakeAws::new();
        let owner = Uuid::new_v4();
        let (a, b, c) = (Uuid::new_v4(), Uuid::new_v4(), Uuid::new_v4());
        let mut page1 = scan_response(vec![
            file_item(a, owner, "a", T1, true),
            file_item(b, owner, "b", T3, true),
        ]);
        page1["LastEvaluatedKey"] = json!({"id": {"S": b.to_string()}});
        fake.respond_json("Scan", page1);
        fake.respond_json(
            "Scan",
            scan_response(vec![file_item(c, owner, "c", T2, true)]),
        );

        let files = fake
            .metadata_client()
            .list_trashed(Some(owner))
            .await
            .unwrap();
        let ids: Vec<_> = files.iter().map(|f| f.id).collect();
        assert_eq!(ids, vec![b, c, a]);

        let scans = fake.requests_for("Scan");
        assert_eq!(scans.len(), 2);
        let first = scans[0].json();
        assert_eq!(
            first["FilterExpression"],
            "is_trashed = :trashed AND owner_id = :owner_id"
        );
        assert_eq!(first["ExpressionAttributeValues"][":trashed"]["BOOL"], true);
        assert_eq!(
            scans[1].json()["ExclusiveStartKey"]["id"]["S"],
            b.to_string()
        );
    }

    #[actix_rt::test]
    async fn list_trashed_without_owner_only_filters_trash() {
        let fake = FakeAws::new();
        fake.respond_json("Scan", scan_response(vec![]));
        assert!(fake
            .metadata_client()
            .list_trashed(None)
            .await
            .unwrap()
            .is_empty());
        assert_eq!(
            only(&fake, "Scan")["FilterExpression"],
            "is_trashed = :trashed"
        );
    }

    #[actix_rt::test]
    async fn list_files_builds_filter_from_all_criteria() {
        let fake = FakeAws::new();
        fake.respond_json("Scan", scan_response(vec![]));
        let (folder, owner) = (Uuid::new_v4(), Uuid::new_v4());
        fake.metadata_client()
            .list_files(Some(folder), Some(owner), false)
            .await
            .unwrap();
        let body = only(&fake, "Scan");
        assert_eq!(
            body["FilterExpression"],
            "folder_id = :folder_id AND owner_id = :owner_id AND is_trashed = :trashed"
        );
        let values = &body["ExpressionAttributeValues"];
        assert_eq!(values[":folder_id"]["S"], folder.to_string());
        assert_eq!(values[":owner_id"]["S"], owner.to_string());
        assert_eq!(values[":trashed"]["BOOL"], false);
    }

    #[actix_rt::test]
    async fn list_files_without_criteria_scans_unfiltered() {
        let fake = FakeAws::new();
        fake.respond_json("Scan", scan_response(vec![]));
        fake.metadata_client()
            .list_files(None, None, true)
            .await
            .unwrap();
        let body = only(&fake, "Scan");
        assert!(body.get("FilterExpression").is_none());
        assert!(body.get("ExpressionAttributeValues").is_none());
    }

    #[actix_rt::test]
    async fn list_files_follows_pagination() {
        let fake = FakeAws::new();
        let owner = Uuid::new_v4();
        let (a, b) = (Uuid::new_v4(), Uuid::new_v4());
        let mut page1 = scan_response(vec![file_item(a, owner, "a", T1, false)]);
        page1["LastEvaluatedKey"] = json!({"id": {"S": a.to_string()}});
        fake.respond_json("Scan", page1);
        fake.respond_json(
            "Scan",
            scan_response(vec![file_item(b, owner, "b", T2, false)]),
        );
        let files = fake
            .metadata_client()
            .list_files(None, Some(owner), false)
            .await
            .unwrap();
        assert_eq!(files.iter().map(|f| f.id).collect::<Vec<_>>(), vec![a, b]);
        assert_eq!(fake.requests_for("Scan").len(), 2);
    }

    #[actix_rt::test]
    async fn list_files_propagates_parse_and_sdk_errors() {
        let fake = FakeAws::new();
        fake.respond_json("Scan", scan_response(vec![json!({"id": {"S": "bad"}})]));
        let err = expect_err(fake.metadata_client().list_files(None, None, true).await);
        assert!(matches!(err, ServiceError::DynamoError(_)), "{err:?}");

        let fake = FakeAws::new();
        fake.dynamo_error("Scan", "InternalServerError");
        let err = expect_err(fake.metadata_client().list_files(None, None, true).await);
        assert!(matches!(err, ServiceError::DynamoError(_)), "{err:?}");
    }

    // -- folders --

    #[actix_rt::test]
    async fn put_folder_writes_parent_when_present() {
        let fake = FakeAws::new();
        fake.respond_json("PutItem", json!({}));
        fake.respond_json("PutItem", json!({}));
        let parent = Uuid::new_v4();
        let mut folder = Folder {
            id: Uuid::new_v4(),
            name: "Docs".into(),
            parent_id: Some(parent),
            owner_id: Uuid::new_v4(),
            created_at: ts(T1),
            updated_at: ts(T1),
        };
        let meta = fake.metadata_client();
        meta.put_folder(&folder).await.unwrap();
        folder.parent_id = None;
        meta.put_folder(&folder).await.unwrap();

        let reqs = fake.requests_for("PutItem");
        let with_parent = reqs[0].json();
        assert_eq!(with_parent["TableName"], "folders");
        assert_eq!(with_parent["Item"]["name"]["S"], "Docs");
        assert_eq!(with_parent["Item"]["parent_id"]["S"], parent.to_string());
        assert!(reqs[1].json()["Item"].get("parent_id").is_none());
    }

    #[actix_rt::test]
    async fn get_folder_found_and_missing() {
        let fake = FakeAws::new();
        let (id, owner) = (Uuid::new_v4(), Uuid::new_v4());
        fake.respond_json(
            "GetItem",
            get_item_response(folder_item(id, owner, "Docs", None)),
        );
        fake.respond_json("GetItem", json!({}));
        let meta = fake.metadata_client();
        assert_eq!(meta.get_folder(&id).await.unwrap().name, "Docs");
        let err = expect_err(meta.get_folder(&id).await);
        assert!(matches!(err, ServiceError::FolderNotFound(_)), "{err:?}");
        assert_eq!(
            fake.requests_for("GetItem")[0].json()["TableName"],
            "folders"
        );
    }

    #[actix_rt::test]
    async fn update_folder_sets_name_and_parent() {
        let fake = FakeAws::new();
        let (id, owner, parent) = (Uuid::new_v4(), Uuid::new_v4(), Uuid::new_v4());
        fake.respond_json("UpdateItem", json!({}));
        fake.respond_json(
            "GetItem",
            get_item_response(folder_item(id, owner, "New", Some(parent))),
        );
        let folder = fake
            .metadata_client()
            .update_folder(&id, Some("New".into()), Some(parent))
            .await
            .unwrap();
        assert_eq!(folder.parent_id, Some(parent));
        let body = only(&fake, "UpdateItem");
        assert_eq!(
            body["UpdateExpression"],
            "SET updated_at = :u, #n = :n, parent_id = :p"
        );
        assert_eq!(body["ExpressionAttributeNames"]["#n"], "name");
        assert_eq!(body["ExpressionAttributeValues"][":n"]["S"], "New");
        assert_eq!(
            body["ExpressionAttributeValues"][":p"]["S"],
            parent.to_string()
        );
    }

    #[actix_rt::test]
    async fn update_folder_with_no_changes_only_touches_timestamp() {
        let fake = FakeAws::new();
        let (id, owner) = (Uuid::new_v4(), Uuid::new_v4());
        fake.respond_json("UpdateItem", json!({}));
        fake.respond_json(
            "GetItem",
            get_item_response(folder_item(id, owner, "Same", None)),
        );
        fake.metadata_client()
            .update_folder(&id, None, None)
            .await
            .unwrap();
        let body = only(&fake, "UpdateItem");
        assert_eq!(body["UpdateExpression"], "SET updated_at = :u");
        assert!(body.get("ExpressionAttributeNames").is_none());
    }

    #[actix_rt::test]
    async fn update_folder_errors() {
        let fake = FakeAws::new();
        fake.dynamo_error("UpdateItem", "ConditionalCheckFailedException");
        fake.dynamo_error("UpdateItem", "InternalServerError");
        let meta = fake.metadata_client();
        let id = Uuid::new_v4();
        let err = expect_err(meta.update_folder(&id, None, None).await);
        assert!(matches!(err, ServiceError::FolderNotFound(_)), "{err:?}");
        let err = expect_err(meta.update_folder(&id, None, None).await);
        assert!(matches!(err, ServiceError::DynamoError(_)), "{err:?}");
    }

    #[actix_rt::test]
    async fn delete_folder_deletes_by_id() {
        let fake = FakeAws::new();
        fake.respond_json("DeleteItem", json!({}));
        let id = Uuid::new_v4();
        fake.metadata_client().delete_folder(&id).await.unwrap();
        let body = only(&fake, "DeleteItem");
        assert_eq!(body["TableName"], "folders");
        assert_eq!(body["Key"]["id"]["S"], id.to_string());
    }

    #[actix_rt::test]
    async fn list_folders_root_uses_attribute_not_exists() {
        let fake = FakeAws::new();
        let owner = Uuid::new_v4();
        fake.respond_json(
            "Scan",
            scan_response(vec![folder_item(Uuid::new_v4(), owner, "A", None)]),
        );
        let folders = fake
            .metadata_client()
            .list_folders(None, Some(owner))
            .await
            .unwrap();
        assert_eq!(folders.len(), 1);
        assert_eq!(
            only(&fake, "Scan")["FilterExpression"],
            "attribute_not_exists(parent_id) AND owner_id = :owner_id"
        );
    }

    #[actix_rt::test]
    async fn list_folders_by_parent() {
        let fake = FakeAws::new();
        fake.respond_json("Scan", scan_response(vec![]));
        let parent = Uuid::new_v4();
        fake.metadata_client()
            .list_folders(Some(parent), None)
            .await
            .unwrap();
        let body = only(&fake, "Scan");
        assert_eq!(body["FilterExpression"], "parent_id = :parent_id");
        assert_eq!(
            body["ExpressionAttributeValues"][":parent_id"]["S"],
            parent.to_string()
        );
    }

    // -- versions --

    #[actix_rt::test]
    async fn put_version_writes_item() {
        let fake = FakeAws::new();
        fake.respond_json("PutItem", json!({}));
        let v = FileVersion {
            file_id: Uuid::new_v4(),
            version: 3,
            s3_key: "k".into(),
            size_bytes: 10,
            created_by: Uuid::new_v4(),
            created_at: ts(T1),
        };
        fake.metadata_client().put_version(&v).await.unwrap();
        let body = only(&fake, "PutItem");
        assert_eq!(body["TableName"], "versions");
        assert_eq!(body["Item"]["version"]["N"], "3");
        assert_eq!(body["Item"]["file_id"]["S"], v.file_id.to_string());
    }

    #[actix_rt::test]
    async fn list_versions_queries_newest_first() {
        let fake = FakeAws::new();
        let (file, user) = (Uuid::new_v4(), Uuid::new_v4());
        fake.respond_json(
            "Query",
            json!({"Items": [version_item(file, 2, user), version_item(file, 1, user)], "Count": 2}),
        );
        let versions = fake.metadata_client().list_versions(&file).await.unwrap();
        assert_eq!(
            versions.iter().map(|v| v.version).collect::<Vec<_>>(),
            vec![2, 1]
        );
        let body = only(&fake, "Query");
        assert_eq!(body["TableName"], "versions");
        assert_eq!(body["KeyConditionExpression"], "file_id = :fid");
        assert_eq!(body["ScanIndexForward"], false);
    }

    // -- shares --

    #[actix_rt::test]
    async fn put_share_writes_permission_as_lowercase() {
        let fake = FakeAws::new();
        fake.respond_json("PutItem", json!({}));
        let share = FileShare {
            id: Uuid::new_v4(),
            file_id: Uuid::new_v4(),
            shared_with: Uuid::new_v4(),
            permission: SharePermission::Viewer,
            shared_by: Uuid::new_v4(),
            created_at: ts(T1),
        };
        fake.metadata_client().put_share(&share).await.unwrap();
        let body = only(&fake, "PutItem");
        assert_eq!(body["TableName"], "shares");
        assert_eq!(body["Item"]["permission"]["S"], "viewer");
        assert_eq!(
            body["Item"]["shared_with"]["S"],
            share.shared_with.to_string()
        );
    }

    #[actix_rt::test]
    async fn find_existing_share_none_and_some() {
        let fake = FakeAws::new();
        let (file, user, owner, sid) = (
            Uuid::new_v4(),
            Uuid::new_v4(),
            Uuid::new_v4(),
            Uuid::new_v4(),
        );
        fake.respond_json("Scan", scan_response(vec![]));
        fake.respond_json(
            "Scan",
            scan_response(vec![share_item(sid, file, user, "editor", owner, T1)]),
        );
        let meta = fake.metadata_client();
        assert!(meta
            .find_existing_share(&file, &user)
            .await
            .unwrap()
            .is_none());
        let found = meta
            .find_existing_share(&file, &user)
            .await
            .unwrap()
            .unwrap();
        assert_eq!(found.id, sid);
        assert_eq!(found.permission, SharePermission::Editor);

        let body = fake.requests_for("Scan")[0].json();
        assert_eq!(
            body["FilterExpression"],
            "file_id = :fid AND shared_with = :uid"
        );
        assert_eq!(
            body["ExpressionAttributeValues"][":uid"]["S"],
            user.to_string()
        );
    }

    #[actix_rt::test]
    async fn share_listings_use_expected_filters() {
        let fake = FakeAws::new();
        let (file, user, owner) = (Uuid::new_v4(), Uuid::new_v4(), Uuid::new_v4());
        let item = share_item(Uuid::new_v4(), file, user, "viewer", owner, T1);
        for _ in 0..3 {
            fake.respond_json("Scan", scan_response(vec![item.clone()]));
        }
        let meta = fake.metadata_client();
        assert_eq!(meta.list_shares_for_user(&user).await.unwrap().len(), 1);
        assert_eq!(meta.list_shares_by_owner(&owner).await.unwrap().len(), 1);
        assert_eq!(meta.list_shares(&file).await.unwrap().len(), 1);

        let filters: Vec<_> = fake
            .requests_for("Scan")
            .iter()
            .map(|r| r.json()["FilterExpression"].as_str().unwrap().to_string())
            .collect();
        assert_eq!(
            filters,
            vec!["shared_with = :uid", "shared_by = :uid", "file_id = :fid"]
        );
    }

    #[actix_rt::test]
    async fn share_listings_propagate_errors() {
        let fake = FakeAws::new();
        for _ in 0..4 {
            fake.dynamo_error("Scan", "InternalServerError");
        }
        let meta = fake.metadata_client();
        let id = Uuid::new_v4();
        assert!(meta.list_shares_for_user(&id).await.is_err());
        assert!(meta.list_shares_by_owner(&id).await.is_err());
        assert!(meta.list_shares(&id).await.is_err());
        assert!(meta.find_existing_share(&id, &id).await.is_err());
    }

    #[actix_rt::test]
    async fn delete_share_deletes_by_share_id() {
        let fake = FakeAws::new();
        fake.respond_json("DeleteItem", json!({}));
        let id = Uuid::new_v4();
        fake.metadata_client().delete_share(&id).await.unwrap();
        let body = only(&fake, "DeleteItem");
        assert_eq!(body["TableName"], "shares");
        assert_eq!(body["Key"]["id"]["S"], id.to_string());
    }
}
