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

/// Level of access a caller needs on a file.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FileAccess {
    /// Owner, or any user the file is shared with.
    Read,
    /// Owner only (move, rename, trash, restore, delete, share management).
    Owner,
}

/// Decide whether `caller` may access `file` at `access` level given the
/// share record (if any) that names the caller. Denials surface as
/// `FileNotFound` so an unauthorized caller cannot tell whether the id exists.
pub fn authorize_file_access(
    file: &FileMetadata,
    caller_share: Option<&FileShare>,
    caller: &Uuid,
    access: FileAccess,
) -> Result<(), ServiceError> {
    if file.owner_id == *caller {
        return Ok(());
    }
    let shared = caller_share.is_some_and(|s| s.file_id == file.id && s.shared_with == *caller);
    match access {
        FileAccess::Read if shared => Ok(()),
        _ => Err(ServiceError::FileNotFound(file.id.to_string())),
    }
}

pub fn authorize_folder_access(folder: &Folder, caller: &Uuid) -> Result<(), ServiceError> {
    if folder.owner_id == *caller {
        Ok(())
    } else {
        Err(ServiceError::FolderNotFound(folder.id.to_string()))
    }
}

const OWNED_CONDITION: &str = "attribute_exists(id) AND owner_id = :owner";

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

    /// Load a file only if `caller` is allowed `access` to it.
    pub async fn get_file_for(
        &self,
        file_id: &Uuid,
        caller: &Uuid,
        access: FileAccess,
    ) -> Result<FileMetadata, ServiceError> {
        let file = self.get_file(file_id).await?;
        if file.owner_id == *caller {
            return Ok(file);
        }
        let caller_share = match access {
            FileAccess::Read => self.find_existing_share(file_id, caller).await?,
            FileAccess::Owner => None,
        };
        authorize_file_access(&file, caller_share.as_ref(), caller, access)?;
        Ok(file)
    }

    /// Delete a file record, but only if it is owned by `owner`.
    pub async fn delete_file(&self, file_id: &Uuid, owner: &Uuid) -> Result<(), ServiceError> {
        self.client
            .delete_item()
            .table_name(&self.files_table)
            .key("id", AttributeValue::S(file_id.to_string()))
            .condition_expression(OWNED_CONDITION)
            .expression_attribute_values(":owner", AttributeValue::S(owner.to_string()))
            .send()
            .await
            .map_err(|e| {
                if is_conditional_check_failed(&e) {
                    return ServiceError::FileNotFound(file_id.to_string());
                }
                ServiceError::DynamoError(e.to_string())
            })?;
        Ok(())
    }

    pub async fn trash_file(
        &self,
        file_id: &Uuid,
        owner: &Uuid,
    ) -> Result<FileMetadata, ServiceError> {
        let now = Utc::now();
        self.client
            .update_item()
            .table_name(&self.files_table)
            .key("id", AttributeValue::S(file_id.to_string()))
            .update_expression("SET is_trashed = :t, updated_at = :u")
            .condition_expression(OWNED_CONDITION)
            .expression_attribute_values(":owner", AttributeValue::S(owner.to_string()))
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

    pub async fn restore_file(
        &self,
        file_id: &Uuid,
        owner: &Uuid,
    ) -> Result<FileMetadata, ServiceError> {
        let now = Utc::now();
        self.client
            .update_item()
            .table_name(&self.files_table)
            .key("id", AttributeValue::S(file_id.to_string()))
            .update_expression("SET is_trashed = :t, updated_at = :u")
            .condition_expression(OWNED_CONDITION)
            .expression_attribute_values(":owner", AttributeValue::S(owner.to_string()))
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
        owner: &Uuid,
        name: &str,
    ) -> Result<FileMetadata, ServiceError> {
        let now = Utc::now();
        self.client
            .update_item()
            .table_name(&self.files_table)
            .key("id", AttributeValue::S(file_id.to_string()))
            .update_expression("SET #n = :n, updated_at = :u")
            .condition_expression(OWNED_CONDITION)
            .expression_attribute_values(":owner", AttributeValue::S(owner.to_string()))
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
        owner: &Uuid,
        folder_id: Option<Uuid>,
    ) -> Result<FileMetadata, ServiceError> {
        let now = Utc::now();
        let mut update_builder = self
            .client
            .update_item()
            .table_name(&self.files_table)
            .key("id", AttributeValue::S(file_id.to_string()))
            .condition_expression(OWNED_CONDITION)
            .expression_attribute_values(":owner", AttributeValue::S(owner.to_string()))
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

    /// Load a folder only if it is owned by `caller`.
    pub async fn get_folder_for(
        &self,
        folder_id: &Uuid,
        caller: &Uuid,
    ) -> Result<Folder, ServiceError> {
        let folder = self.get_folder(folder_id).await?;
        authorize_folder_access(&folder, caller)?;
        Ok(folder)
    }

    pub async fn update_folder(
        &self,
        folder_id: &Uuid,
        owner: &Uuid,
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
            .condition_expression(OWNED_CONDITION)
            .expression_attribute_values(":owner", AttributeValue::S(owner.to_string()))
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

    /// Delete a folder record, but only if it is owned by `owner`.
    pub async fn delete_folder(&self, folder_id: &Uuid, owner: &Uuid) -> Result<(), ServiceError> {
        self.client
            .delete_item()
            .table_name(&self.folders_table)
            .key("id", AttributeValue::S(folder_id.to_string()))
            .condition_expression(OWNED_CONDITION)
            .expression_attribute_values(":owner", AttributeValue::S(owner.to_string()))
            .send()
            .await
            .map_err(|e| {
                if is_conditional_check_failed(&e) {
                    return ServiceError::FolderNotFound(folder_id.to_string());
                }
                ServiceError::DynamoError(e.to_string())
            })?;
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

    fn sample_file(owner: Uuid) -> FileMetadata {
        let now = Utc::now();
        FileMetadata {
            id: Uuid::new_v4(),
            name: "report.pdf".into(),
            mime_type: "application/pdf".into(),
            size_bytes: 10,
            s3_key: "files/x".into(),
            folder_id: None,
            owner_id: owner,
            version: 1,
            is_trashed: false,
            created_at: now,
            updated_at: now,
        }
    }

    fn sample_share(
        file: &FileMetadata,
        shared_with: Uuid,
        permission: SharePermission,
    ) -> FileShare {
        FileShare {
            id: Uuid::new_v4(),
            file_id: file.id,
            shared_with,
            permission,
            shared_by: file.owner_id,
            created_at: Utc::now(),
        }
    }

    #[test]
    fn owner_has_every_access_level() {
        let owner = Uuid::new_v4();
        let file = sample_file(owner);
        assert!(authorize_file_access(&file, None, &owner, FileAccess::Read).is_ok());
        assert!(authorize_file_access(&file, None, &owner, FileAccess::Owner).is_ok());
    }

    #[test]
    fn stranger_is_denied_as_not_found() {
        let file = sample_file(Uuid::new_v4());
        let attacker = Uuid::new_v4();
        for access in [FileAccess::Read, FileAccess::Owner] {
            let err = authorize_file_access(&file, None, &attacker, access).unwrap_err();
            assert!(matches!(err, ServiceError::FileNotFound(_)), "{access:?}");
        }
    }

    #[test]
    fn share_grants_read_but_not_owner_access() {
        let file = sample_file(Uuid::new_v4());
        let viewer = Uuid::new_v4();
        for permission in [SharePermission::Viewer, SharePermission::Editor] {
            let share = sample_share(&file, viewer, permission);
            assert!(authorize_file_access(&file, Some(&share), &viewer, FileAccess::Read).is_ok());
            assert!(matches!(
                authorize_file_access(&file, Some(&share), &viewer, FileAccess::Owner),
                Err(ServiceError::FileNotFound(_))
            ));
        }
    }

    #[test]
    fn share_for_someone_else_does_not_grant_access() {
        let file = sample_file(Uuid::new_v4());
        let share = sample_share(&file, Uuid::new_v4(), SharePermission::Editor);
        let attacker = Uuid::new_v4();
        assert!(matches!(
            authorize_file_access(&file, Some(&share), &attacker, FileAccess::Read),
            Err(ServiceError::FileNotFound(_))
        ));
        let other_file = sample_file(file.owner_id);
        let wrong_file_share = sample_share(&other_file, attacker, SharePermission::Editor);
        assert!(matches!(
            authorize_file_access(&file, Some(&wrong_file_share), &attacker, FileAccess::Read),
            Err(ServiceError::FileNotFound(_))
        ));
    }

    #[test]
    fn folder_access_is_owner_only() {
        let owner = Uuid::new_v4();
        let now = Utc::now();
        let folder = Folder {
            id: Uuid::new_v4(),
            name: "docs".into(),
            parent_id: None,
            owner_id: owner,
            created_at: now,
            updated_at: now,
        };
        assert!(authorize_folder_access(&folder, &owner).is_ok());
        assert!(matches!(
            authorize_folder_access(&folder, &Uuid::new_v4()),
            Err(ServiceError::FolderNotFound(_))
        ));
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
