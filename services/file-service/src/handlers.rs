use actix_multipart::Multipart;
use actix_web::{web, HttpRequest, HttpResponse};
use bytes::BytesMut;
use chrono::Utc;
use futures_util::StreamExt;
use uuid::Uuid;

async fn chaos_active(cm: &mut redis::aio::ConnectionManager, flag: &str) -> bool {
    let result: redis::RedisResult<i64> = redis::cmd("EXISTS").arg(flag).query_async(cm).await;
    result.unwrap_or(0) > 0
}

use crate::config::AppConfig;
use crate::errors::ServiceError;
use crate::events::EventPublisher;
use crate::metadata::MetadataClient;
use crate::middleware;
use crate::models::{
    ActivityItem, ActivityQuery, ActivityResponse, CreateFolderRequest, DownloadResponse,
    FileDetailResponse, FileMetadata, FileShare, FileVersion, Folder, HealthResponse,
    ListFilesQuery, ListFilesResponse, ListFoldersQuery, ListFoldersResponse, ListVersionsResponse,
    MoveFileRequest, RenameFileRequest, ShareFileRequest, ShareFileResponse, UpdateFolderRequest,
    UploadResponse,
};
use crate::storage::S3Client;

// -- Health & Metrics --

pub async fn health() -> HttpResponse {
    HttpResponse::Ok().json(HealthResponse {
        status: "healthy".into(),
        service: "file-service".into(),
        version: env!("CARGO_PKG_VERSION").into(),
    })
}

pub async fn metrics() -> HttpResponse {
    HttpResponse::Ok()
        .content_type("text/plain; charset=utf-8")
        .body(middleware::render_metrics())
}

// -- File Handlers --

pub async fn upload_file(
    req: HttpRequest,
    s3: web::Data<S3Client>,
    meta: web::Data<MetadataClient>,
    events: web::Data<EventPublisher>,
    config: web::Data<AppConfig>,
    redis_cm: web::Data<redis::aio::ConnectionManager>,
    mut payload: Multipart,
) -> Result<HttpResponse, ServiceError> {
    // Prefer owner_id from X-User-ID header (injected by api-gateway from JWT).
    // Fall back to the multipart field for direct/internal callers.
    let header_owner_id = req
        .headers()
        .get("X-User-ID")
        .and_then(|v| v.to_str().ok())
        .and_then(|s| s.trim().parse::<Uuid>().ok());

    let mut file_bytes = BytesMut::new();
    let mut file_name = String::from("unnamed");
    let mut content_type = String::from("application/octet-stream");
    let mut owner_id: Option<Uuid> = None;
    let mut folder_id: Option<Uuid> = None;

    while let Some(item) = payload.next().await {
        let mut field = item.map_err(|e| ServiceError::BadRequest(e.to_string()))?;
        let disposition = field.content_disposition().cloned();
        let field_name = disposition
            .as_ref()
            .and_then(|d| d.get_name().map(|s| s.to_string()))
            .unwrap_or_default();

        match field_name.as_str() {
            "file" => {
                if let Some(fname) = disposition.as_ref().and_then(|d| d.get_filename()) {
                    file_name = fname.to_string();
                }
                if let Some(ct) = field.content_type() {
                    content_type = ct.to_string();
                }
                while let Some(chunk) = field.next().await {
                    let data = chunk.map_err(|e| ServiceError::BadRequest(e.to_string()))?;
                    file_bytes.extend_from_slice(&data);
                    if file_bytes.len() as u64 > config.server.max_upload_bytes {
                        return Err(ServiceError::FileTooLarge {
                            max_bytes: config.server.max_upload_bytes,
                            actual_bytes: file_bytes.len() as u64,
                        });
                    }
                }
            }
            "owner_id" => {
                let mut value = BytesMut::new();
                while let Some(chunk) = field.next().await {
                    let data = chunk.map_err(|e| ServiceError::BadRequest(e.to_string()))?;
                    value.extend_from_slice(&data);
                }
                let s = String::from_utf8_lossy(&value).to_string();
                owner_id = Some(
                    s.trim()
                        .parse::<Uuid>()
                        .map_err(|e| ServiceError::BadRequest(format!("invalid owner_id: {e}")))?,
                );
            }
            "folder_id" => {
                let mut value = BytesMut::new();
                while let Some(chunk) = field.next().await {
                    let data = chunk.map_err(|e| ServiceError::BadRequest(e.to_string()))?;
                    value.extend_from_slice(&data);
                }
                let s = String::from_utf8_lossy(&value).to_string();
                let trimmed = s.trim();
                if !trimmed.is_empty() {
                    folder_id = Some(trimmed.parse::<Uuid>().map_err(|e| {
                        ServiceError::BadRequest(format!("invalid folder_id: {e}"))
                    })?);
                }
            }
            _ => {}
        }
    }

    let owner = header_owner_id
        .or(owner_id)
        .ok_or_else(|| ServiceError::BadRequest("owner_id is required".into()))?;

    if file_bytes.is_empty() {
        return Err(ServiceError::BadRequest("file field is required".into()));
    }

    let file_id = Uuid::new_v4();
    let s3_key = format!("files/{}/{}", owner, file_id);
    let now = Utc::now();
    let size = file_bytes.len() as u64;

    // CHAOS: when this flag is active the S3 client targets a nonexistent
    // bucket, simulating a misconfigured bucket name after a recent infra
    // change.  The AWS SDK returns NoSuchBucket which surfaces as a 500.
    let effective_bucket = if chaos_active(
        &mut redis_cm.get_ref().clone(),
        "chaos:file-service:upload_s3_error",
    )
    .await
    {
        tracing::warn!("Chaos flag active: redirecting upload to nonexistent bucket");
        "otterworks-files-chaos-nonexistent".to_string()
    } else {
        s3.bucket.clone()
    };
    let chaos_s3 = crate::storage::S3Client {
        client: s3.client.clone(),
        bucket: effective_bucket,
    };
    chaos_s3
        .upload_object(&s3_key, file_bytes.freeze(), &content_type)
        .await?;

    let file_meta = FileMetadata {
        id: file_id,
        name: file_name,
        mime_type: content_type,
        size_bytes: size,
        s3_key: s3_key.clone(),
        folder_id,
        owner_id: owner,
        version: 1,
        is_trashed: false,
        created_at: now,
        updated_at: now,
    };

    meta.put_file(&file_meta).await?;

    let version = FileVersion {
        file_id,
        version: 1,
        s3_key,
        size_bytes: size,
        created_by: owner,
        created_at: now,
    };
    meta.put_version(&version).await?;

    let _ = events
        .file_uploaded(
            &file_id,
            &owner,
            folder_id.as_ref(),
            &file_meta.name,
            &file_meta.mime_type,
            file_meta.size_bytes,
        )
        .await;

    tracing::info!(file_id = %file_id, name = %file_meta.name, size = %size, "File uploaded");

    Ok(HttpResponse::Created().json(UploadResponse { file: file_meta }))
}

pub async fn get_file_metadata(
    meta: web::Data<MetadataClient>,
    path: web::Path<String>,
) -> Result<HttpResponse, ServiceError> {
    let file_id: Uuid = path
        .into_inner()
        .parse()
        .map_err(|e| ServiceError::BadRequest(format!("invalid file id: {e}")))?;
    let file = meta.get_file(&file_id).await?;
    let shares = meta.list_shares(&file_id).await.unwrap_or_default();
    Ok(HttpResponse::Ok().json(FileDetailResponse {
        file,
        shared_with: shares,
    }))
}

/// Resolve the effective owner_id for list operations.
///
/// Prefer the `X-User-ID` header injected by the api-gateway from the
/// authenticated JWT. This prevents a caller from spoofing another user's
/// `owner_id` via the query string. Fall back to `query.owner_id` only when
/// no header is present (direct/internal callers).
fn resolve_owner_id(req: &HttpRequest, query_owner_id: Option<Uuid>) -> Option<Uuid> {
    let header_owner_id = req
        .headers()
        .get("X-User-ID")
        .and_then(|v| v.to_str().ok())
        .and_then(|s| s.trim().parse::<Uuid>().ok());

    header_owner_id.or(query_owner_id)
}

pub async fn list_files(
    req: HttpRequest,
    meta: web::Data<MetadataClient>,
    query: web::Query<ListFilesQuery>,
) -> Result<HttpResponse, ServiceError> {
    let include_trashed = query.include_trashed.unwrap_or(false);
    let owner_id = resolve_owner_id(&req, query.owner_id);
    let files = meta
        .list_files(query.folder_id, owner_id, include_trashed)
        .await?;

    let page = query.page.unwrap_or(1).max(1);
    let page_size = query.page_size.unwrap_or(50).min(100);
    let total = files.len();
    let start = (page - 1).saturating_mul(page_size) as usize;
    let paged: Vec<FileMetadata> = files
        .into_iter()
        .skip(start)
        .take(page_size as usize)
        .collect();

    Ok(HttpResponse::Ok().json(ListFilesResponse {
        files: paged,
        total,
        page,
        page_size,
    }))
}

pub async fn list_shared_files(
    meta: web::Data<MetadataClient>,
    req: HttpRequest,
    query: web::Query<ListFilesQuery>,
) -> Result<HttpResponse, ServiceError> {
    let user_id: Uuid = req
        .headers()
        .get("X-User-ID")
        .and_then(|v| v.to_str().ok())
        .and_then(|s| s.parse().ok())
        .ok_or_else(|| ServiceError::BadRequest("missing X-User-ID header".into()))?;

    let shares = meta.list_shares_for_user(&user_id).await?;

    // Deduplicate by file_id to handle legacy duplicate share records
    let mut seen_file_ids = std::collections::HashSet::new();
    let mut files = Vec::new();
    for share in &shares {
        if !seen_file_ids.insert(share.file_id) {
            continue;
        }
        match meta.get_file(&share.file_id).await {
            Ok(file) if !file.is_trashed => files.push(file),
            _ => {}
        }
    }

    let page = query.page.unwrap_or(1).max(1);
    let page_size = query.page_size.unwrap_or(50).min(100);
    let total = files.len();
    let start = (page - 1).saturating_mul(page_size) as usize;
    let paged: Vec<FileMetadata> = files
        .into_iter()
        .skip(start)
        .take(page_size as usize)
        .collect();

    Ok(HttpResponse::Ok().json(ListFilesResponse {
        files: paged,
        total,
        page,
        page_size,
    }))
}

pub async fn list_trashed(
    req: HttpRequest,
    meta: web::Data<MetadataClient>,
    query: web::Query<ListFilesQuery>,
) -> Result<HttpResponse, ServiceError> {
    let owner_id = resolve_owner_id(&req, query.owner_id);
    let files = meta.list_trashed(owner_id).await?;

    let page = query.page.unwrap_or(1).max(1);
    let page_size = query.page_size.unwrap_or(50).min(100);
    let total = files.len();
    let start = (page - 1).saturating_mul(page_size) as usize;
    let paged: Vec<FileMetadata> = files
        .into_iter()
        .skip(start)
        .take(page_size as usize)
        .collect();

    Ok(HttpResponse::Ok().json(ListFilesResponse {
        files: paged,
        total,
        page,
        page_size,
    }))
}
pub async fn delete_file(
    s3: web::Data<S3Client>,
    meta: web::Data<MetadataClient>,
    events: web::Data<EventPublisher>,
    path: web::Path<String>,
) -> Result<HttpResponse, ServiceError> {
    let file_id: Uuid = path
        .into_inner()
        .parse()
        .map_err(|e| ServiceError::BadRequest(format!("invalid file id: {e}")))?;

    let file = meta.get_file(&file_id).await?;
    meta.delete_file(&file_id).await?;
    s3.delete_object(&file.s3_key).await?;

    let _ = events.file_deleted(&file_id, &file.owner_id).await;

    tracing::info!(file_id = %file_id, "File deleted");
    Ok(HttpResponse::NoContent().finish())
}

pub async fn download_file(
    s3: web::Data<S3Client>,
    meta: web::Data<MetadataClient>,
    path: web::Path<String>,
) -> Result<HttpResponse, ServiceError> {
    let file_id: Uuid = path
        .into_inner()
        .parse()
        .map_err(|e| ServiceError::BadRequest(format!("invalid file id: {e}")))?;

    let file = meta.get_file(&file_id).await?;
    let url = s3.presigned_download_url(&file.s3_key, 3600).await?;

    Ok(HttpResponse::Ok().json(DownloadResponse {
        url,
        expires_in_secs: 3600,
    }))
}

pub async fn move_file(
    meta: web::Data<MetadataClient>,
    events: web::Data<EventPublisher>,
    path: web::Path<String>,
    body: web::Json<MoveFileRequest>,
) -> Result<HttpResponse, ServiceError> {
    let file_id: Uuid = path
        .into_inner()
        .parse()
        .map_err(|e| ServiceError::BadRequest(format!("invalid file id: {e}")))?;

    let file = meta.move_file(&file_id, body.folder_id).await?;

    let _ = events
        .file_moved(&file_id, &file.owner_id, body.folder_id.as_ref())
        .await;

    tracing::info!(file_id = %file_id, folder_id = ?body.folder_id, "File moved");
    Ok(HttpResponse::Ok().json(file))
}

pub async fn rename_file(
    meta: web::Data<MetadataClient>,
    events: web::Data<EventPublisher>,
    path: web::Path<String>,
    body: web::Json<RenameFileRequest>,
) -> Result<HttpResponse, ServiceError> {
    let file_id: Uuid = path
        .into_inner()
        .parse()
        .map_err(|e| ServiceError::BadRequest(format!("invalid file id: {e}")))?;

    let name = body.name.trim();
    if name.is_empty() {
        return Err(ServiceError::BadRequest("name cannot be empty".into()));
    }

    let file = meta.rename_file(&file_id, name).await?;

    let _ = events
        .file_updated(
            &file_id,
            &file.owner_id,
            file.folder_id.as_ref(),
            &file.name,
            &file.mime_type,
            file.size_bytes as u64,
        )
        .await;

    tracing::info!(file_id = %file_id, new_name = %name, "File renamed");
    Ok(HttpResponse::Ok().json(file))
}

pub async fn list_versions(
    meta: web::Data<MetadataClient>,
    path: web::Path<String>,
) -> Result<HttpResponse, ServiceError> {
    let file_id: Uuid = path
        .into_inner()
        .parse()
        .map_err(|e| ServiceError::BadRequest(format!("invalid file id: {e}")))?;

    let versions = meta.list_versions(&file_id).await?;
    Ok(HttpResponse::Ok().json(ListVersionsResponse { versions }))
}

pub async fn trash_file(
    meta: web::Data<MetadataClient>,
    events: web::Data<EventPublisher>,
    path: web::Path<String>,
) -> Result<HttpResponse, ServiceError> {
    let file_id: Uuid = path
        .into_inner()
        .parse()
        .map_err(|e| ServiceError::BadRequest(format!("invalid file id: {e}")))?;

    let file = meta.trash_file(&file_id).await?;

    let _ = events.file_trashed(&file_id, &file.owner_id).await;

    tracing::info!(file_id = %file_id, "File trashed");
    Ok(HttpResponse::Ok().json(file))
}

pub async fn restore_file(
    meta: web::Data<MetadataClient>,
    events: web::Data<EventPublisher>,
    path: web::Path<String>,
) -> Result<HttpResponse, ServiceError> {
    let file_id: Uuid = path
        .into_inner()
        .parse()
        .map_err(|e| ServiceError::BadRequest(format!("invalid file id: {e}")))?;

    let file = meta.restore_file(&file_id).await?;

    let _ = events
        .file_restored(
            &file_id,
            &file.owner_id,
            file.folder_id.as_ref(),
            &file.name,
            &file.mime_type,
            file.size_bytes as u64,
        )
        .await;

    tracing::info!(file_id = %file_id, "File restored");
    Ok(HttpResponse::Ok().json(file))
}

pub async fn share_file(
    meta: web::Data<MetadataClient>,
    events: web::Data<EventPublisher>,
    path: web::Path<String>,
    body: web::Json<ShareFileRequest>,
) -> Result<HttpResponse, ServiceError> {
    let file_id: Uuid = path
        .into_inner()
        .parse()
        .map_err(|e| ServiceError::BadRequest(format!("invalid file id: {e}")))?;

    // Ensure file exists
    let file = meta.get_file(&file_id).await?;

    // Check if share already exists for this file + user
    if let Some(existing) = meta
        .find_existing_share(&file_id, &body.shared_with)
        .await?
    {
        // Update permission if different, otherwise return existing
        if existing.permission != body.permission {
            let updated = FileShare {
                id: existing.id,
                file_id,
                shared_with: body.shared_with,
                permission: body.permission.clone(),
                shared_by: body.shared_by,
                created_at: existing.created_at,
            };
            meta.put_share(&updated).await?;
            tracing::info!(file_id = %file_id, shared_with = %body.shared_with, "File share updated");
            return Ok(HttpResponse::Ok().json(ShareFileResponse { share: updated }));
        }
        tracing::info!(file_id = %file_id, shared_with = %body.shared_with, "File already shared");
        return Ok(HttpResponse::Ok().json(ShareFileResponse { share: existing }));
    }

    let share = FileShare {
        id: Uuid::new_v4(),
        file_id,
        shared_with: body.shared_with,
        permission: body.permission.clone(),
        shared_by: body.shared_by,
        created_at: Utc::now(),
    };

    meta.put_share(&share).await?;

    let _ = events
        .file_shared(&file_id, &file.owner_id, &body.shared_with)
        .await;

    tracing::info!(file_id = %file_id, shared_with = %body.shared_with, "File shared");
    Ok(HttpResponse::Created().json(ShareFileResponse { share }))
}

pub async fn remove_share(
    meta: web::Data<MetadataClient>,
    path: web::Path<(String, String)>,
) -> Result<HttpResponse, ServiceError> {
    let (file_id_str, user_id_str) = path.into_inner();
    let file_id: Uuid = file_id_str
        .parse()
        .map_err(|e| ServiceError::BadRequest(format!("invalid file id: {e}")))?;
    let user_id: Uuid = user_id_str
        .parse()
        .map_err(|e| ServiceError::BadRequest(format!("invalid user id: {e}")))?;

    // Ensure file exists
    let _file = meta.get_file(&file_id).await?;

    // Find the existing share
    let share = meta
        .find_existing_share(&file_id, &user_id)
        .await?
        .ok_or_else(|| ServiceError::ShareNotFound("Share not found".into()))?;

    meta.delete_share(&share.id).await?;

    tracing::info!(file_id = %file_id, user_id = %user_id, "File share removed");
    Ok(HttpResponse::NoContent().finish())
}

// -- Folder Handlers --

pub async fn list_folders(
    req: HttpRequest,
    meta: web::Data<MetadataClient>,
    query: web::Query<ListFoldersQuery>,
) -> Result<HttpResponse, ServiceError> {
    let owner_id = resolve_owner_id(&req, query.owner_id);
    let folders = meta.list_folders(query.parent_id, owner_id).await?;
    Ok(HttpResponse::Ok().json(ListFoldersResponse { folders }))
}

pub async fn create_folder(
    meta: web::Data<MetadataClient>,
    body: web::Json<CreateFolderRequest>,
) -> Result<HttpResponse, ServiceError> {
    let now = Utc::now();
    let folder = Folder {
        id: Uuid::new_v4(),
        name: body.name.clone(),
        parent_id: body.parent_id,
        owner_id: body.owner_id,
        created_at: now,
        updated_at: now,
    };

    meta.put_folder(&folder).await?;
    tracing::info!(folder_id = %folder.id, name = %folder.name, "Folder created");
    Ok(HttpResponse::Created().json(folder))
}

pub async fn get_folder(
    meta: web::Data<MetadataClient>,
    path: web::Path<String>,
) -> Result<HttpResponse, ServiceError> {
    let folder_id: Uuid = path
        .into_inner()
        .parse()
        .map_err(|e| ServiceError::BadRequest(format!("invalid folder id: {e}")))?;

    let folder = meta.get_folder(&folder_id).await?;
    Ok(HttpResponse::Ok().json(folder))
}

pub async fn update_folder(
    meta: web::Data<MetadataClient>,
    path: web::Path<String>,
    body: web::Json<UpdateFolderRequest>,
) -> Result<HttpResponse, ServiceError> {
    let folder_id: Uuid = path
        .into_inner()
        .parse()
        .map_err(|e| ServiceError::BadRequest(format!("invalid folder id: {e}")))?;

    let folder = meta
        .update_folder(&folder_id, body.name.clone(), body.parent_id)
        .await?;
    Ok(HttpResponse::Ok().json(folder))
}

pub async fn delete_folder(
    meta: web::Data<MetadataClient>,
    path: web::Path<String>,
) -> Result<HttpResponse, ServiceError> {
    let folder_id: Uuid = path
        .into_inner()
        .parse()
        .map_err(|e| ServiceError::BadRequest(format!("invalid folder id: {e}")))?;

    meta.delete_folder(&folder_id).await?;
    tracing::info!(folder_id = %folder_id, "Folder deleted");
    Ok(HttpResponse::NoContent().finish())
}

// -- Activity Handler --

pub async fn list_activity(
    req: HttpRequest,
    meta: web::Data<MetadataClient>,
    query: web::Query<ActivityQuery>,
) -> Result<HttpResponse, ServiceError> {
    let owner_id = req
        .headers()
        .get("X-User-ID")
        .and_then(|v| v.to_str().ok())
        .and_then(|s| s.trim().parse::<Uuid>().ok())
        .ok_or_else(|| ServiceError::BadRequest("missing owner context".into()))?;

    let limit = query.limit.unwrap_or(20).min(50) as usize;

    let (files, shares) = futures_util::future::join(
        meta.list_files(None, Some(owner_id), true),
        meta.list_shares_by_owner(&owner_id),
    )
    .await;

    let files = files.unwrap_or_default();
    let shares = shares.unwrap_or_default();

    // Build a file-id → name lookup for share descriptions
    let file_names: std::collections::HashMap<Uuid, String> =
        files.iter().map(|f| (f.id, f.name.clone())).collect();

    let mut items: Vec<ActivityItem> = Vec::new();

    for f in &files {
        items.push(ActivityItem {
            id: format!("upload-{}", f.id),
            activity_type: "upload".into(),
            description: format!("Uploaded {}", f.name),
            actor_name: "You".into(),
            resource_name: f.name.clone(),
            resource_type: "file".into(),
            resource_id: f.id.to_string(),
            created_at: f.created_at.to_rfc3339(),
        });
    }

    for s in &shares {
        let name = file_names
            .get(&s.file_id)
            .cloned()
            .unwrap_or_else(|| "a file".into());
        items.push(ActivityItem {
            id: format!("share-{}", s.id),
            activity_type: "share".into(),
            description: format!("Shared {}", name),
            actor_name: "You".into(),
            resource_name: name,
            resource_type: "file".into(),
            resource_id: s.file_id.to_string(),
            created_at: s.created_at.to_rfc3339(),
        });
    }

    items.sort_by(|a, b| b.created_at.cmp(&a.created_at));
    items.truncate(limit);

    Ok(HttpResponse::Ok().json(ActivityResponse { items }))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[actix_rt::test]
    async fn test_health_endpoint() {
        let resp = health().await;
        assert_eq!(resp.status(), actix_web::http::StatusCode::OK);
    }

    #[actix_rt::test]
    async fn test_metrics_endpoint() {
        let resp = metrics().await;
        assert_eq!(resp.status(), actix_web::http::StatusCode::OK);
    }
}

#[cfg(test)]
mod api_tests {
    use super::*;
    use crate::test_support::{
        file_item, folder_item, get_item_response, scan_response, share_item, version_item, FakeAws,
    };
    use actix_web::http::StatusCode;
    use actix_web::{test, App};
    use serde_json::{json, Value};

    const T1: &str = "2024-01-01T00:00:00+00:00";
    const T2: &str = "2024-02-01T00:00:00+00:00";
    const T3: &str = "2024-03-01T00:00:00+00:00";

    /// Same routes as `main`, minus `/upload`, which is tested separately with a fake Redis.
    fn routes(cfg: &mut web::ServiceConfig) {
        cfg.service(
            web::scope("/api/v1/files")
                .route("/shared", web::get().to(list_shared_files))
                .route("/trash", web::get().to(list_trashed))
                .route("/activity", web::get().to(list_activity))
                .route("", web::get().to(list_files))
                .route("/{file_id}", web::get().to(get_file_metadata))
                .route("/{file_id}", web::delete().to(delete_file))
                .route("/{file_id}/download", web::get().to(download_file))
                .route("/{file_id}/move", web::put().to(move_file))
                .route("/{file_id}/rename", web::patch().to(rename_file))
                .route("/{file_id}/versions", web::get().to(list_versions))
                .route("/{file_id}/trash", web::post().to(trash_file))
                .route("/{file_id}/restore", web::post().to(restore_file))
                .route("/{file_id}/share", web::post().to(share_file))
                .route("/{file_id}/share/{user_id}", web::delete().to(remove_share)),
        )
        .service(
            web::scope("/api/v1/folders")
                .route("", web::get().to(list_folders))
                .route("", web::post().to(create_folder))
                .route("/{folder_id}", web::get().to(get_folder))
                .route("/{folder_id}", web::put().to(update_folder))
                .route("/{folder_id}", web::delete().to(delete_folder)),
        );
    }

    async fn call(fake: &FakeAws, req: test::TestRequest) -> (StatusCode, Value) {
        let app = test::init_service(
            App::new()
                .app_data(web::Data::new(fake.metadata_client()))
                .app_data(web::Data::new(fake.s3_client()))
                .app_data(web::Data::new(EventPublisher::from_client(
                    fake.sns(),
                    None,
                )))
                .configure(routes),
        )
        .await;
        let resp = test::call_service(&app, req.to_request()).await;
        let status = resp.status();
        let bytes = test::read_body(resp).await;
        let body = if bytes.is_empty() {
            Value::Null
        } else {
            serde_json::from_slice(&bytes)
                .unwrap_or(Value::String(String::from_utf8_lossy(&bytes).to_string()))
        };
        (status, body)
    }

    fn get(uri: &str) -> test::TestRequest {
        test::TestRequest::get().uri(uri)
    }

    fn file_json(id: Uuid, owner: Uuid, name: &str, at: &str, trashed: bool) -> Value {
        get_item_response(file_item(id, owner, name, at, trashed))
    }

    // -- path validation --

    #[actix_rt::test]
    async fn invalid_ids_are_rejected_before_any_backend_call() {
        let ok = Uuid::new_v4();
        let share_body = json!({"shared_with": ok, "permission": "viewer", "shared_by": ok});
        let cases: Vec<(test::TestRequest, &str)> = vec![
            (get("/api/v1/files/bad"), "invalid file id"),
            (
                test::TestRequest::delete().uri("/api/v1/files/bad"),
                "invalid file id",
            ),
            (get("/api/v1/files/bad/download"), "invalid file id"),
            (
                test::TestRequest::put()
                    .uri("/api/v1/files/bad/move")
                    .set_json(json!({})),
                "invalid file id",
            ),
            (
                test::TestRequest::patch()
                    .uri("/api/v1/files/bad/rename")
                    .set_json(json!({"name": "x"})),
                "invalid file id",
            ),
            (get("/api/v1/files/bad/versions"), "invalid file id"),
            (
                test::TestRequest::post().uri("/api/v1/files/bad/trash"),
                "invalid file id",
            ),
            (
                test::TestRequest::post().uri("/api/v1/files/bad/restore"),
                "invalid file id",
            ),
            (
                test::TestRequest::post()
                    .uri("/api/v1/files/bad/share")
                    .set_json(share_body),
                "invalid file id",
            ),
            (
                test::TestRequest::delete().uri(&format!("/api/v1/files/bad/share/{ok}")),
                "invalid file id",
            ),
            (
                test::TestRequest::delete().uri(&format!("/api/v1/files/{ok}/share/bad")),
                "invalid user id",
            ),
            (get("/api/v1/folders/bad"), "invalid folder id"),
            (
                test::TestRequest::put()
                    .uri("/api/v1/folders/bad")
                    .set_json(json!({})),
                "invalid folder id",
            ),
            (
                test::TestRequest::delete().uri("/api/v1/folders/bad"),
                "invalid folder id",
            ),
        ];
        for (req, msg) in cases {
            let fake = FakeAws::new();
            let (status, body) = call(&fake, req).await;
            assert_eq!(status, StatusCode::BAD_REQUEST, "{body}");
            assert_eq!(body["error"], "bad_request");
            assert!(body["message"].as_str().unwrap().contains(msg), "{body}");
            assert!(fake.requests().is_empty());
        }
    }

    // -- file metadata / download / delete --

    #[actix_rt::test]
    async fn get_file_metadata_includes_shares() {
        let fake = FakeAws::new();
        let (id, owner, user) = (Uuid::new_v4(), Uuid::new_v4(), Uuid::new_v4());
        fake.respond_json("GetItem", file_json(id, owner, "a.txt", T1, false));
        fake.respond_json(
            "Scan",
            scan_response(vec![share_item(
                Uuid::new_v4(),
                id,
                user,
                "viewer",
                owner,
                T1,
            )]),
        );
        let (status, body) = call(&fake, get(&format!("/api/v1/files/{id}"))).await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(body["id"], id.to_string());
        assert_eq!(body["name"], "a.txt");
        assert_eq!(body["shared_with"][0]["shared_with"], user.to_string());
        assert_eq!(body["shared_with"][0]["permission"], "viewer");
    }

    #[actix_rt::test]
    async fn get_file_metadata_tolerates_share_lookup_failure() {
        let fake = FakeAws::new();
        let (id, owner) = (Uuid::new_v4(), Uuid::new_v4());
        fake.respond_json("GetItem", file_json(id, owner, "a.txt", T1, false));
        fake.dynamo_error("Scan", "InternalServerError");
        let (status, body) = call(&fake, get(&format!("/api/v1/files/{id}"))).await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(body["shared_with"], json!([]));
    }

    #[actix_rt::test]
    async fn missing_file_is_404_and_backend_failure_is_500() {
        let fake = FakeAws::new();
        fake.respond_json("GetItem", json!({}));
        let id = Uuid::new_v4();
        let (status, body) = call(&fake, get(&format!("/api/v1/files/{id}"))).await;
        assert_eq!(status, StatusCode::NOT_FOUND);
        assert_eq!(body["error"], "file_not_found");

        let fake = FakeAws::new();
        fake.dynamo_error("GetItem", "InternalServerError");
        let (status, body) = call(&fake, get(&format!("/api/v1/files/{id}"))).await;
        assert_eq!(status, StatusCode::INTERNAL_SERVER_ERROR);
        assert_eq!(body["error"], "metadata_error");
    }

    #[actix_rt::test]
    async fn download_returns_presigned_url() {
        let fake = FakeAws::new();
        let (id, owner) = (Uuid::new_v4(), Uuid::new_v4());
        fake.respond_json("GetItem", file_json(id, owner, "a.txt", T1, false));
        let (status, body) = call(&fake, get(&format!("/api/v1/files/{id}/download"))).await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(body["expires_in_secs"], 3600);
        let url = body["url"].as_str().unwrap();
        assert!(url.contains(&format!("files/{owner}/{id}")), "{url}");
        assert!(url.contains("X-Amz-Expires=3600"), "{url}");
    }

    #[actix_rt::test]
    async fn download_of_missing_file_is_404() {
        let fake = FakeAws::new();
        fake.respond_json("GetItem", json!({}));
        let (status, _) = call(
            &fake,
            get(&format!("/api/v1/files/{}/download", Uuid::new_v4())),
        )
        .await;
        assert_eq!(status, StatusCode::NOT_FOUND);
    }

    #[actix_rt::test]
    async fn delete_file_removes_metadata_then_blob() {
        let fake = FakeAws::new();
        let (id, owner) = (Uuid::new_v4(), Uuid::new_v4());
        fake.respond_json("GetItem", file_json(id, owner, "a.txt", T1, false));
        fake.respond_json("DeleteItem", json!({}));
        fake.respond("DELETE", 204, "");
        let (status, body) = call(
            &fake,
            test::TestRequest::delete().uri(&format!("/api/v1/files/{id}")),
        )
        .await;
        assert_eq!(status, StatusCode::NO_CONTENT);
        assert_eq!(body, Value::Null);
        let ops: Vec<_> = fake.requests().into_iter().map(|r| r.op).collect();
        assert_eq!(ops, vec!["GetItem", "DeleteItem", "DELETE"]);
        assert!(fake.requests_for("DELETE")[0]
            .uri
            .contains(&format!("files/{owner}/{id}")));
    }

    #[actix_rt::test]
    async fn delete_file_storage_failure_is_500() {
        let fake = FakeAws::new();
        let (id, owner) = (Uuid::new_v4(), Uuid::new_v4());
        fake.respond_json("GetItem", file_json(id, owner, "a.txt", T1, false));
        fake.respond_json("DeleteItem", json!({}));
        fake.respond(
            "DELETE",
            403,
            "<Error><Code>AccessDenied</Code><Message>no</Message></Error>",
        );
        let (status, body) = call(
            &fake,
            test::TestRequest::delete().uri(&format!("/api/v1/files/{id}")),
        )
        .await;
        assert_eq!(status, StatusCode::INTERNAL_SERVER_ERROR);
        assert_eq!(body["error"], "storage_error");
    }

    // -- rename / move / versions / trash --

    #[actix_rt::test]
    async fn rename_rejects_blank_names() {
        for name in ["", "   ", "\t\n"] {
            let fake = FakeAws::new();
            let (status, body) = call(
                &fake,
                test::TestRequest::patch()
                    .uri(&format!("/api/v1/files/{}/rename", Uuid::new_v4()))
                    .set_json(json!({ "name": name })),
            )
            .await;
            assert_eq!(status, StatusCode::BAD_REQUEST);
            assert_eq!(body["message"], "Bad request: name cannot be empty");
            assert!(fake.requests().is_empty());
        }
    }

    #[actix_rt::test]
    async fn rename_trims_name_before_saving() {
        let fake = FakeAws::new();
        let (id, owner) = (Uuid::new_v4(), Uuid::new_v4());
        fake.respond_json("UpdateItem", json!({}));
        fake.respond_json("GetItem", file_json(id, owner, "new.txt", T2, false));
        let (status, body) = call(
            &fake,
            test::TestRequest::patch()
                .uri(&format!("/api/v1/files/{id}/rename"))
                .set_json(json!({"name": "  new.txt  "})),
        )
        .await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(body["name"], "new.txt");
        assert_eq!(
            fake.requests_for("UpdateItem")[0].json()["ExpressionAttributeValues"][":n"]["S"],
            "new.txt"
        );
    }

    #[actix_rt::test]
    async fn rename_of_missing_file_is_404() {
        let fake = FakeAws::new();
        fake.dynamo_error("UpdateItem", "ConditionalCheckFailedException");
        let (status, body) = call(
            &fake,
            test::TestRequest::patch()
                .uri(&format!("/api/v1/files/{}/rename", Uuid::new_v4()))
                .set_json(json!({"name": "x"})),
        )
        .await;
        assert_eq!(status, StatusCode::NOT_FOUND);
        assert_eq!(body["error"], "file_not_found");
    }

    #[actix_rt::test]
    async fn rename_requires_json_name() {
        let fake = FakeAws::new();
        let (status, _) = call(
            &fake,
            test::TestRequest::patch()
                .uri(&format!("/api/v1/files/{}/rename", Uuid::new_v4()))
                .set_json(json!({"title": "x"})),
        )
        .await;
        assert_eq!(status, StatusCode::BAD_REQUEST);
        assert!(fake.requests().is_empty());
    }

    #[actix_rt::test]
    async fn move_file_returns_updated_file() {
        let fake = FakeAws::new();
        let (id, owner, folder) = (Uuid::new_v4(), Uuid::new_v4(), Uuid::new_v4());
        fake.respond_json("UpdateItem", json!({}));
        fake.respond_json("GetItem", file_json(id, owner, "a", T2, false));
        let (status, body) = call(
            &fake,
            test::TestRequest::put()
                .uri(&format!("/api/v1/files/{id}/move"))
                .set_json(json!({ "folder_id": folder })),
        )
        .await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(body["id"], id.to_string());
        assert_eq!(
            fake.requests_for("UpdateItem")[0].json()["ExpressionAttributeValues"][":f"]["S"],
            folder.to_string()
        );
    }

    #[actix_rt::test]
    async fn list_versions_wraps_versions() {
        let fake = FakeAws::new();
        let (id, user) = (Uuid::new_v4(), Uuid::new_v4());
        fake.respond_json(
            "Query",
            json!({"Items": [version_item(id, 2, user), version_item(id, 1, user)]}),
        );
        let (status, body) = call(&fake, get(&format!("/api/v1/files/{id}/versions"))).await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(body["versions"].as_array().unwrap().len(), 2);
        assert_eq!(body["versions"][0]["version"], 2);
    }

    #[actix_rt::test]
    async fn trash_and_restore_return_file() {
        for (action, trashed) in [("trash", true), ("restore", false)] {
            let fake = FakeAws::new();
            let (id, owner) = (Uuid::new_v4(), Uuid::new_v4());
            fake.respond_json("UpdateItem", json!({}));
            fake.respond_json("GetItem", file_json(id, owner, "a", T2, trashed));
            let (status, body) = call(
                &fake,
                test::TestRequest::post().uri(&format!("/api/v1/files/{id}/{action}")),
            )
            .await;
            assert_eq!(status, StatusCode::OK, "{action}");
            assert_eq!(body["is_trashed"], trashed, "{action}");
        }
    }

    #[actix_rt::test]
    async fn trash_of_missing_file_is_404() {
        let fake = FakeAws::new();
        fake.dynamo_error("UpdateItem", "ConditionalCheckFailedException");
        let (status, _) = call(
            &fake,
            test::TestRequest::post().uri(&format!("/api/v1/files/{}/trash", Uuid::new_v4())),
        )
        .await;
        assert_eq!(status, StatusCode::NOT_FOUND);
    }

    // -- sharing --

    fn share_req(file: Uuid, with: Uuid, by: Uuid, permission: &str) -> test::TestRequest {
        test::TestRequest::post()
            .uri(&format!("/api/v1/files/{file}/share"))
            .set_json(json!({"shared_with": with, "permission": permission, "shared_by": by}))
    }

    #[actix_rt::test]
    async fn share_creates_new_share() {
        let fake = FakeAws::new();
        let (file, owner, with) = (Uuid::new_v4(), Uuid::new_v4(), Uuid::new_v4());
        fake.respond_json("GetItem", file_json(file, owner, "a", T1, false));
        fake.respond_json("Scan", scan_response(vec![]));
        fake.respond_json("PutItem", json!({}));
        let (status, body) = call(&fake, share_req(file, with, owner, "editor")).await;
        assert_eq!(status, StatusCode::CREATED);
        assert_eq!(body["share"]["file_id"], file.to_string());
        assert_eq!(body["share"]["shared_with"], with.to_string());
        assert_eq!(body["share"]["permission"], "editor");
        let put = fake.requests_for("PutItem")[0].json();
        assert_eq!(put["Item"]["id"]["S"], body["share"]["id"]);
    }

    #[actix_rt::test]
    async fn share_with_same_permission_returns_existing() {
        let fake = FakeAws::new();
        let (file, owner, with, sid) = (
            Uuid::new_v4(),
            Uuid::new_v4(),
            Uuid::new_v4(),
            Uuid::new_v4(),
        );
        fake.respond_json("GetItem", file_json(file, owner, "a", T1, false));
        fake.respond_json(
            "Scan",
            scan_response(vec![share_item(sid, file, with, "viewer", owner, T1)]),
        );
        let (status, body) = call(&fake, share_req(file, with, owner, "viewer")).await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(body["share"]["id"], sid.to_string());
        assert!(fake.requests_for("PutItem").is_empty());
    }

    #[actix_rt::test]
    async fn share_with_new_permission_updates_existing() {
        let fake = FakeAws::new();
        let (file, owner, with, sid) = (
            Uuid::new_v4(),
            Uuid::new_v4(),
            Uuid::new_v4(),
            Uuid::new_v4(),
        );
        fake.respond_json("GetItem", file_json(file, owner, "a", T1, false));
        fake.respond_json(
            "Scan",
            scan_response(vec![share_item(sid, file, with, "viewer", owner, T1)]),
        );
        fake.respond_json("PutItem", json!({}));
        let (status, body) = call(&fake, share_req(file, with, owner, "editor")).await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(body["share"]["id"], sid.to_string());
        assert_eq!(body["share"]["permission"], "editor");
        assert_eq!(body["share"]["created_at"], "2024-01-01T00:00:00Z");
        let put = fake.requests_for("PutItem")[0].json();
        assert_eq!(put["Item"]["id"]["S"], sid.to_string());
        assert_eq!(put["Item"]["permission"]["S"], "editor");
    }

    #[actix_rt::test]
    async fn share_of_missing_file_is_404() {
        let fake = FakeAws::new();
        fake.respond_json("GetItem", json!({}));
        let id = Uuid::new_v4();
        let (status, body) = call(&fake, share_req(id, id, id, "viewer")).await;
        assert_eq!(status, StatusCode::NOT_FOUND);
        assert_eq!(body["error"], "file_not_found");
        assert!(fake.requests_for("Scan").is_empty());
    }

    #[actix_rt::test]
    async fn share_rejects_unknown_permission() {
        let fake = FakeAws::new();
        let id = Uuid::new_v4();
        let (status, _) = call(&fake, share_req(id, id, id, "owner")).await;
        assert_eq!(status, StatusCode::BAD_REQUEST);
        assert!(fake.requests().is_empty());
    }

    #[actix_rt::test]
    async fn remove_share_deletes_existing_share() {
        let fake = FakeAws::new();
        let (file, owner, user, sid) = (
            Uuid::new_v4(),
            Uuid::new_v4(),
            Uuid::new_v4(),
            Uuid::new_v4(),
        );
        fake.respond_json("GetItem", file_json(file, owner, "a", T1, false));
        fake.respond_json(
            "Scan",
            scan_response(vec![share_item(sid, file, user, "viewer", owner, T1)]),
        );
        fake.respond_json("DeleteItem", json!({}));
        let (status, _) = call(
            &fake,
            test::TestRequest::delete().uri(&format!("/api/v1/files/{file}/share/{user}")),
        )
        .await;
        assert_eq!(status, StatusCode::NO_CONTENT);
        assert_eq!(
            fake.requests_for("DeleteItem")[0].json()["Key"]["id"]["S"],
            sid.to_string()
        );
    }

    #[actix_rt::test]
    async fn remove_missing_share_is_404() {
        let fake = FakeAws::new();
        let (file, owner, user) = (Uuid::new_v4(), Uuid::new_v4(), Uuid::new_v4());
        fake.respond_json("GetItem", file_json(file, owner, "a", T1, false));
        fake.respond_json("Scan", scan_response(vec![]));
        let (status, body) = call(
            &fake,
            test::TestRequest::delete().uri(&format!("/api/v1/files/{file}/share/{user}")),
        )
        .await;
        assert_eq!(status, StatusCode::NOT_FOUND);
        assert_eq!(body["error"], "share_not_found");
        assert!(fake.requests_for("DeleteItem").is_empty());
    }

    // -- listings and pagination --

    fn files_page(owner: Uuid, n: usize) -> Value {
        scan_response(
            (0..n)
                .map(|i| file_item(Uuid::new_v4(), owner, &format!("f{i}"), T1, false))
                .collect(),
        )
    }

    #[actix_rt::test]
    async fn list_files_defaults_to_first_page_of_50() {
        let fake = FakeAws::new();
        fake.respond_json("Scan", files_page(Uuid::new_v4(), 3));
        let (status, body) = call(&fake, get("/api/v1/files")).await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(body["total"], 3);
        assert_eq!(body["page"], 1);
        assert_eq!(body["page_size"], 50);
        assert_eq!(body["files"].as_array().unwrap().len(), 3);
        let scan = fake.requests_for("Scan")[0].json();
        assert_eq!(scan["FilterExpression"], "is_trashed = :trashed");
    }

    #[actix_rt::test]
    async fn list_files_paginates_and_clamps() {
        let owner = Uuid::new_v4();
        let cases = [
            ("page=2&page_size=2", 2, 2, vec!["f2", "f3"]),
            ("page=3&page_size=2", 3, 2, vec!["f4"]),
            ("page=9&page_size=2", 9, 2, vec![]),
            ("page=0&page_size=1", 1, 1, vec!["f0"]),
            ("page_size=1000", 1, 100, vec!["f0", "f1", "f2", "f3", "f4"]),
        ];
        for (query, page, page_size, names) in cases {
            let fake = FakeAws::new();
            fake.respond_json("Scan", files_page(owner, 5));
            let (status, body) = call(&fake, get(&format!("/api/v1/files?{query}"))).await;
            assert_eq!(status, StatusCode::OK, "{query}");
            assert_eq!(body["page"], page, "{query}");
            assert_eq!(body["page_size"], page_size, "{query}");
            assert_eq!(body["total"], 5, "{query}");
            let got: Vec<_> = body["files"]
                .as_array()
                .unwrap()
                .iter()
                .map(|f| f["name"].as_str().unwrap().to_string())
                .collect();
            assert_eq!(got, names, "{query}");
        }
    }

    #[actix_rt::test]
    async fn list_files_prefers_header_owner_over_query() {
        let (header_owner, query_owner) = (Uuid::new_v4(), Uuid::new_v4());
        let fake = FakeAws::new();
        fake.respond_json("Scan", files_page(header_owner, 0));
        let (status, _) = call(
            &fake,
            get(&format!(
                "/api/v1/files?owner_id={query_owner}&include_trashed=true"
            ))
            .insert_header(("X-User-ID", format!(" {header_owner} "))),
        )
        .await;
        assert_eq!(status, StatusCode::OK);
        let scan = fake.requests_for("Scan")[0].json();
        assert_eq!(scan["FilterExpression"], "owner_id = :owner_id");
        assert_eq!(
            scan["ExpressionAttributeValues"][":owner_id"]["S"],
            header_owner.to_string()
        );
    }

    #[actix_rt::test]
    async fn list_files_falls_back_to_query_owner_on_bad_header() {
        let query_owner = Uuid::new_v4();
        let fake = FakeAws::new();
        fake.respond_json("Scan", files_page(query_owner, 0));
        call(
            &fake,
            get(&format!("/api/v1/files?owner_id={query_owner}"))
                .insert_header(("X-User-ID", "not-a-uuid")),
        )
        .await;
        let scan = fake.requests_for("Scan")[0].json();
        assert_eq!(
            scan["ExpressionAttributeValues"][":owner_id"]["S"],
            query_owner.to_string()
        );
    }

    #[actix_rt::test]
    async fn list_files_backend_failure_is_500() {
        let fake = FakeAws::new();
        fake.dynamo_error("Scan", "InternalServerError");
        let (status, body) = call(&fake, get("/api/v1/files")).await;
        assert_eq!(status, StatusCode::INTERNAL_SERVER_ERROR);
        assert_eq!(body["error"], "metadata_error");
    }

    #[actix_rt::test]
    async fn list_shared_requires_user_header() {
        let fake = FakeAws::new();
        let (status, body) = call(&fake, get("/api/v1/files/shared")).await;
        assert_eq!(status, StatusCode::BAD_REQUEST);
        assert_eq!(body["message"], "Bad request: missing X-User-ID header");
        assert!(fake.requests().is_empty());
    }

    #[actix_rt::test]
    async fn list_shared_dedupes_and_skips_trashed_or_missing_files() {
        let fake = FakeAws::new();
        let (user, owner) = (Uuid::new_v4(), Uuid::new_v4());
        let (live, trashed, gone) = (Uuid::new_v4(), Uuid::new_v4(), Uuid::new_v4());
        let share = |f| share_item(Uuid::new_v4(), f, user, "viewer", owner, T1);
        fake.respond_json(
            "Scan",
            scan_response(vec![share(live), share(live), share(trashed), share(gone)]),
        );
        fake.respond_json("GetItem", file_json(live, owner, "live", T1, false));
        fake.respond_json("GetItem", file_json(trashed, owner, "trashed", T1, true));
        fake.respond_json("GetItem", json!({}));
        let (status, body) = call(
            &fake,
            get("/api/v1/files/shared").insert_header(("X-User-ID", user.to_string())),
        )
        .await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(body["total"], 1);
        assert_eq!(body["files"][0]["id"], live.to_string());
        assert_eq!(fake.requests_for("GetItem").len(), 3);
        assert_eq!(
            fake.requests_for("Scan")[0].json()["ExpressionAttributeValues"][":uid"]["S"],
            user.to_string()
        );
    }

    #[actix_rt::test]
    async fn list_shared_paginates() {
        let fake = FakeAws::new();
        let (user, owner) = (Uuid::new_v4(), Uuid::new_v4());
        let files: Vec<Uuid> = (0..3).map(|_| Uuid::new_v4()).collect();
        fake.respond_json(
            "Scan",
            scan_response(
                files
                    .iter()
                    .map(|f| share_item(Uuid::new_v4(), *f, user, "viewer", owner, T1))
                    .collect(),
            ),
        );
        for f in &files {
            fake.respond_json("GetItem", file_json(*f, owner, "x", T1, false));
        }
        let (_, body) = call(
            &fake,
            get("/api/v1/files/shared?page=2&page_size=2")
                .insert_header(("X-User-ID", user.to_string())),
        )
        .await;
        assert_eq!(body["total"], 3);
        assert_eq!(body["page"], 2);
        assert_eq!(body["files"].as_array().unwrap().len(), 1);
        assert_eq!(body["files"][0]["id"], files[2].to_string());
    }

    #[actix_rt::test]
    async fn list_trashed_scopes_to_owner_and_paginates() {
        let fake = FakeAws::new();
        let owner = Uuid::new_v4();
        fake.respond_json(
            "Scan",
            scan_response(vec![
                file_item(Uuid::new_v4(), owner, "old", T1, true),
                file_item(Uuid::new_v4(), owner, "new", T3, true),
            ]),
        );
        let (status, body) = call(
            &fake,
            get("/api/v1/files/trash?page_size=1").insert_header(("X-User-ID", owner.to_string())),
        )
        .await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(body["total"], 2);
        assert_eq!(body["page_size"], 1);
        assert_eq!(body["files"][0]["name"], "new");
        assert_eq!(
            fake.requests_for("Scan")[0].json()["ExpressionAttributeValues"][":owner_id"]["S"],
            owner.to_string()
        );
    }

    // -- folders --

    #[actix_rt::test]
    async fn create_folder_persists_and_returns_201() {
        let fake = FakeAws::new();
        fake.respond_json("PutItem", json!({}));
        let (owner, parent) = (Uuid::new_v4(), Uuid::new_v4());
        let (status, body) = call(
            &fake,
            test::TestRequest::post()
                .uri("/api/v1/folders")
                .set_json(json!({"name": "Docs", "owner_id": owner, "parent_id": parent})),
        )
        .await;
        assert_eq!(status, StatusCode::CREATED);
        assert_eq!(body["name"], "Docs");
        assert_eq!(body["owner_id"], owner.to_string());
        assert_eq!(body["parent_id"], parent.to_string());
        let put = fake.requests_for("PutItem")[0].json();
        assert_eq!(put["Item"]["id"]["S"], body["id"]);
    }

    #[actix_rt::test]
    async fn create_folder_requires_owner() {
        let fake = FakeAws::new();
        let (status, _) = call(
            &fake,
            test::TestRequest::post()
                .uri("/api/v1/folders")
                .set_json(json!({"name": "Docs"})),
        )
        .await;
        assert_eq!(status, StatusCode::BAD_REQUEST);
        assert!(fake.requests().is_empty());
    }

    #[actix_rt::test]
    async fn list_folders_uses_header_owner() {
        let fake = FakeAws::new();
        let owner = Uuid::new_v4();
        fake.respond_json(
            "Scan",
            scan_response(vec![folder_item(Uuid::new_v4(), owner, "A", None)]),
        );
        let (status, body) = call(
            &fake,
            get("/api/v1/folders").insert_header(("X-User-ID", owner.to_string())),
        )
        .await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(body["folders"][0]["name"], "A");
        assert_eq!(
            fake.requests_for("Scan")[0].json()["ExpressionAttributeValues"][":owner_id"]["S"],
            owner.to_string()
        );
    }

    #[actix_rt::test]
    async fn get_update_delete_folder() {
        let (id, owner) = (Uuid::new_v4(), Uuid::new_v4());

        let fake = FakeAws::new();
        fake.respond_json(
            "GetItem",
            get_item_response(folder_item(id, owner, "A", None)),
        );
        let (status, body) = call(&fake, get(&format!("/api/v1/folders/{id}"))).await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(body["id"], id.to_string());

        let fake = FakeAws::new();
        fake.respond_json("GetItem", json!({}));
        let (status, body) = call(&fake, get(&format!("/api/v1/folders/{id}"))).await;
        assert_eq!(status, StatusCode::NOT_FOUND);
        assert_eq!(body["error"], "folder_not_found");

        let fake = FakeAws::new();
        fake.respond_json("UpdateItem", json!({}));
        fake.respond_json(
            "GetItem",
            get_item_response(folder_item(id, owner, "B", None)),
        );
        let (status, body) = call(
            &fake,
            test::TestRequest::put()
                .uri(&format!("/api/v1/folders/{id}"))
                .set_json(json!({"name": "B"})),
        )
        .await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(body["name"], "B");

        let fake = FakeAws::new();
        fake.dynamo_error("UpdateItem", "ConditionalCheckFailedException");
        let (status, _) = call(
            &fake,
            test::TestRequest::put()
                .uri(&format!("/api/v1/folders/{id}"))
                .set_json(json!({"name": "B"})),
        )
        .await;
        assert_eq!(status, StatusCode::NOT_FOUND);

        let fake = FakeAws::new();
        fake.respond_json("DeleteItem", json!({}));
        let (status, _) = call(
            &fake,
            test::TestRequest::delete().uri(&format!("/api/v1/folders/{id}")),
        )
        .await;
        assert_eq!(status, StatusCode::NO_CONTENT);
    }

    // -- activity --

    #[actix_rt::test]
    async fn activity_requires_user_header() {
        let fake = FakeAws::new();
        let (status, body) = call(&fake, get("/api/v1/files/activity")).await;
        assert_eq!(status, StatusCode::BAD_REQUEST);
        assert_eq!(body["message"], "Bad request: missing owner context");
    }

    #[actix_rt::test]
    async fn activity_merges_uploads_and_shares_newest_first() {
        let fake = FakeAws::new();
        let (owner, user) = (Uuid::new_v4(), Uuid::new_v4());
        let (old, new, foreign) = (Uuid::new_v4(), Uuid::new_v4(), Uuid::new_v4());
        let (s1, s2) = (Uuid::new_v4(), Uuid::new_v4());
        fake.respond_json(
            "Scan",
            scan_response(vec![
                file_item(old, owner, "old.txt", T1, false),
                file_item(new, owner, "new.txt", T3, true),
            ]),
        );
        fake.respond_json(
            "Scan",
            scan_response(vec![
                share_item(s1, old, user, "viewer", owner, T2),
                share_item(s2, foreign, user, "viewer", owner, T1),
            ]),
        );
        let (status, body) = call(
            &fake,
            get("/api/v1/files/activity").insert_header(("X-User-ID", owner.to_string())),
        )
        .await;
        assert_eq!(status, StatusCode::OK);
        let items = body["items"].as_array().unwrap();
        let ids: Vec<_> = items.iter().map(|i| i["id"].as_str().unwrap()).collect();
        assert_eq!(
            ids,
            vec![
                format!("upload-{new}"),
                format!("share-{s1}"),
                format!("upload-{old}"),
                format!("share-{s2}"),
            ]
        );
        assert_eq!(items[0]["type"], "upload");
        assert_eq!(items[0]["description"], "Uploaded new.txt");
        assert_eq!(items[1]["type"], "share");
        assert_eq!(items[1]["description"], "Shared old.txt");
        assert_eq!(items[1]["resource_id"], old.to_string());
        assert_eq!(items[3]["resource_name"], "a file");
        assert_eq!(items[3]["actor_name"], "You");

        // includes trashed files and scopes both scans to the caller
        let scans = fake.requests_for("Scan");
        let file_scan = scans
            .iter()
            .map(|r| r.json())
            .find(|b| b["TableName"] == "files")
            .unwrap();
        assert_eq!(file_scan["FilterExpression"], "owner_id = :owner_id");
        let share_scan = scans
            .iter()
            .map(|r| r.json())
            .find(|b| b["TableName"] == "shares")
            .unwrap();
        assert_eq!(share_scan["FilterExpression"], "shared_by = :uid");
    }

    #[actix_rt::test]
    async fn activity_limit_defaults_to_20_and_caps_at_50() {
        let owner = Uuid::new_v4();
        for (query, expected) in [("", 20), ("?limit=5", 5), ("?limit=500", 50)] {
            let fake = FakeAws::new();
            fake.respond_json("Scan", files_page(owner, 60));
            fake.respond_json("Scan", scan_response(vec![]));
            let (_, body) = call(
                &fake,
                get(&format!("/api/v1/files/activity{query}"))
                    .insert_header(("X-User-ID", owner.to_string())),
            )
            .await;
            assert_eq!(body["items"].as_array().unwrap().len(), expected, "{query}");
        }
    }

    #[actix_rt::test]
    async fn activity_tolerates_backend_failures() {
        let fake = FakeAws::new();
        fake.dynamo_error("Scan", "InternalServerError");
        fake.dynamo_error("Scan", "InternalServerError");
        let (status, body) = call(
            &fake,
            get("/api/v1/files/activity").insert_header(("X-User-ID", Uuid::new_v4().to_string())),
        )
        .await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(body["items"], json!([]));
    }

    // -- upload --

    const BOUNDARY: &str = "XTESTBOUNDARY";
    const CHAOS_FLAG: &str = "chaos:file-service:upload_s3_error";

    enum Part<'a> {
        File {
            filename: Option<&'a str>,
            content_type: Option<&'a str>,
            data: &'a [u8],
        },
        Field(&'a str, &'a str),
    }

    fn multipart(parts: &[Part]) -> Vec<u8> {
        let mut body = Vec::new();
        for part in parts {
            body.extend_from_slice(format!("--{BOUNDARY}\r\n").as_bytes());
            match part {
                Part::File {
                    filename,
                    content_type,
                    data,
                } => {
                    let fname = filename
                        .map(|f| format!("; filename=\"{f}\""))
                        .unwrap_or_default();
                    body.extend_from_slice(
                        format!("Content-Disposition: form-data; name=\"file\"{fname}\r\n")
                            .as_bytes(),
                    );
                    if let Some(ct) = content_type {
                        body.extend_from_slice(format!("Content-Type: {ct}\r\n").as_bytes());
                    }
                    body.extend_from_slice(b"\r\n");
                    body.extend_from_slice(data);
                }
                Part::Field(name, value) => {
                    body.extend_from_slice(
                        format!("Content-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}")
                            .as_bytes(),
                    );
                }
            }
            body.extend_from_slice(b"\r\n");
        }
        body.extend_from_slice(format!("--{BOUNDARY}--\r\n").as_bytes());
        body
    }

    fn upload_req(parts: &[Part]) -> test::TestRequest {
        test::TestRequest::post()
            .uri("/api/v1/files/upload")
            .insert_header((
                "content-type",
                format!("multipart/form-data; boundary={BOUNDARY}"),
            ))
            .set_payload(multipart(parts))
    }

    fn test_config(max_upload_bytes: u64) -> AppConfig {
        use crate::config::{AwsConfig, ServerConfig, SnsConfig};
        AppConfig {
            server: ServerConfig {
                port: 0,
                max_upload_bytes,
            },
            aws: AwsConfig {
                region: "us-east-1".into(),
                endpoint_url: None,
                s3_bucket: crate::test_support::TEST_BUCKET.into(),
                dynamodb_table: "files".into(),
                dynamodb_folders_table: "folders".into(),
                dynamodb_versions_table: "versions".into(),
                dynamodb_shares_table: "shares".into(),
            },
            sns: SnsConfig { topic_arn: None },
        }
    }

    async fn upload_with(
        fake: &FakeAws,
        max_upload_bytes: u64,
        redis_keys: &[&str],
        req: test::TestRequest,
    ) -> (StatusCode, Value) {
        let redis = crate::test_support::fake_redis(redis_keys).await;
        let app = test::init_service(
            App::new()
                .app_data(web::Data::new(fake.metadata_client()))
                .app_data(web::Data::new(fake.s3_client()))
                .app_data(web::Data::new(EventPublisher::from_client(
                    fake.sns(),
                    None,
                )))
                .app_data(web::Data::new(test_config(max_upload_bytes)))
                .app_data(web::Data::new(redis))
                .route("/api/v1/files/upload", web::post().to(upload_file)),
        )
        .await;
        let resp = test::call_service(&app, req.to_request()).await;
        let status = resp.status();
        let bytes = test::read_body(resp).await;
        (
            status,
            serde_json::from_slice(&bytes).unwrap_or(Value::Null),
        )
    }

    fn upload_ok(fake: &FakeAws) {
        fake.respond("PUT", 200, "");
        fake.respond_json("PutItem", json!({}));
        fake.respond_json("PutItem", json!({}));
    }

    #[actix_rt::test]
    async fn upload_stores_blob_metadata_and_first_version() {
        let fake = FakeAws::new();
        upload_ok(&fake);
        let (owner, folder) = (Uuid::new_v4(), Uuid::new_v4());
        let folder_s = folder.to_string();
        let req = upload_req(&[
            Part::Field("folder_id", &folder_s),
            Part::File {
                filename: Some("report.pdf"),
                content_type: Some("application/pdf"),
                data: b"%PDF-1.7",
            },
        ])
        .insert_header(("X-User-ID", owner.to_string()));
        let (status, body) = upload_with(&fake, 1024, &[], req).await;
        assert_eq!(status, StatusCode::CREATED, "{body}");
        let file = &body["file"];
        let id = file["id"].as_str().unwrap();
        assert_eq!(file["name"], "report.pdf");
        assert_eq!(file["mime_type"], "application/pdf");
        assert_eq!(file["size_bytes"], 8);
        assert_eq!(file["owner_id"], owner.to_string());
        assert_eq!(file["folder_id"], folder_s);
        assert_eq!(file["version"], 1);
        assert_eq!(file["is_trashed"], false);
        assert_eq!(file["s3_key"], format!("files/{owner}/{id}"));

        let put = &fake.requests_for("PUT")[0];
        assert!(put.uri.contains(&format!(
            "/{}/files/{owner}/{id}",
            crate::test_support::TEST_BUCKET
        )));
        assert_eq!(put.header("content-type"), Some("application/pdf"));
        assert_eq!(put.header("content-length"), Some("8"));

        let puts = fake.requests_for("PutItem");
        let tables: Vec<_> = puts.iter().map(|r| r.json()["TableName"].clone()).collect();
        assert_eq!(tables, vec![json!("files"), json!("versions")]);
        assert_eq!(puts[1].json()["Item"]["version"]["N"], "1");
        assert_eq!(puts[1].json()["Item"]["file_id"]["S"], id);
    }

    #[actix_rt::test]
    async fn upload_defaults_name_and_content_type() {
        let fake = FakeAws::new();
        upload_ok(&fake);
        let req = upload_req(&[Part::File {
            filename: None,
            content_type: None,
            data: b"abc",
        }])
        .insert_header(("X-User-ID", Uuid::new_v4().to_string()));
        let (status, body) = upload_with(&fake, 1024, &[], req).await;
        assert_eq!(status, StatusCode::CREATED, "{body}");
        assert_eq!(body["file"]["name"], "unnamed");
        assert_eq!(body["file"]["mime_type"], "application/octet-stream");
        assert!(body["file"]["folder_id"].is_null());
        assert_eq!(
            fake.requests_for("PUT")[0].header("content-type"),
            Some("application/octet-stream")
        );
    }

    #[actix_rt::test]
    async fn upload_owner_resolution() {
        let (header_owner, field_owner) = (Uuid::new_v4(), Uuid::new_v4());
        let field = field_owner.to_string();
        let cases = [
            (Some(header_owner.to_string()), header_owner),
            (Some("not-a-uuid".to_string()), field_owner),
            (None, field_owner),
        ];
        for (header, expected) in cases {
            let fake = FakeAws::new();
            upload_ok(&fake);
            let mut req = upload_req(&[
                Part::Field("owner_id", &format!("  {field}  ")),
                Part::File {
                    filename: Some("a"),
                    content_type: None,
                    data: b"x",
                },
            ]);
            if let Some(h) = &header {
                req = req.insert_header(("X-User-ID", h.clone()));
            }
            let (status, body) = upload_with(&fake, 1024, &[], req).await;
            assert_eq!(status, StatusCode::CREATED, "{header:?}: {body}");
            assert_eq!(body["file"]["owner_id"], expected.to_string(), "{header:?}");
        }
    }

    #[actix_rt::test]
    async fn upload_validation_errors() {
        let owner = Uuid::new_v4().to_string();
        let file = || Part::File {
            filename: Some("a"),
            content_type: None,
            data: b"x",
        };
        let cases: Vec<(Vec<Part>, &str)> = vec![
            (vec![file()], "Bad request: owner_id is required"),
            (
                vec![Part::Field("owner_id", &owner)],
                "Bad request: file field is required",
            ),
            (
                vec![
                    Part::Field("owner_id", &owner),
                    Part::File {
                        filename: Some("a"),
                        content_type: None,
                        data: b"",
                    },
                ],
                "Bad request: file field is required",
            ),
            (
                vec![Part::Field("owner_id", "nope"), file()],
                "Bad request: invalid owner_id",
            ),
            (
                vec![
                    Part::Field("owner_id", &owner),
                    Part::Field("folder_id", "nope"),
                    file(),
                ],
                "Bad request: invalid folder_id",
            ),
        ];
        for (parts, msg) in cases {
            let fake = FakeAws::new();
            let (status, body) = upload_with(&fake, 1024, &[], upload_req(&parts)).await;
            assert_eq!(status, StatusCode::BAD_REQUEST, "{msg}");
            assert_eq!(body["error"], "bad_request");
            assert!(body["message"].as_str().unwrap().starts_with(msg), "{body}");
            assert!(fake.requests().is_empty(), "{msg}");
        }
    }

    #[actix_rt::test]
    async fn upload_blank_folder_and_unknown_fields_are_ignored() {
        let fake = FakeAws::new();
        upload_ok(&fake);
        let req = upload_req(&[
            Part::Field("folder_id", "   "),
            Part::Field("description", "ignored"),
            Part::File {
                filename: Some("a"),
                content_type: None,
                data: b"x",
            },
        ])
        .insert_header(("X-User-ID", Uuid::new_v4().to_string()));
        let (status, body) = upload_with(&fake, 1024, &[], req).await;
        assert_eq!(status, StatusCode::CREATED, "{body}");
        assert!(body["file"]["folder_id"].is_null());
    }

    #[actix_rt::test]
    async fn upload_size_limit_is_inclusive() {
        let owner = Uuid::new_v4().to_string();
        for (data, expected) in [
            (&b"1234"[..], StatusCode::CREATED),
            (&b"12345"[..], StatusCode::PAYLOAD_TOO_LARGE),
        ] {
            let fake = FakeAws::new();
            upload_ok(&fake);
            let req = upload_req(&[Part::File {
                filename: Some("a"),
                content_type: None,
                data,
            }])
            .insert_header(("X-User-ID", owner.clone()));
            let (status, body) = upload_with(&fake, 4, &[], req).await;
            assert_eq!(status, expected, "{} bytes: {body}", data.len());
            if expected == StatusCode::PAYLOAD_TOO_LARGE {
                assert_eq!(body["error"], "file_too_large");
                assert_eq!(body["message"], "File too large: max 4 bytes, got 5 bytes");
                assert!(fake.requests().is_empty());
            }
        }
    }

    #[actix_rt::test]
    async fn upload_chaos_flag_redirects_to_missing_bucket() {
        let fake = FakeAws::new();
        fake.respond(
            "PUT",
            404,
            "<Error><Code>NoSuchBucket</Code><Message>missing</Message></Error>",
        );
        let req = upload_req(&[Part::File {
            filename: Some("a"),
            content_type: None,
            data: b"x",
        }])
        .insert_header(("X-User-ID", Uuid::new_v4().to_string()));
        let (status, body) = upload_with(&fake, 1024, &[CHAOS_FLAG], req).await;
        assert_eq!(status, StatusCode::INTERNAL_SERVER_ERROR);
        assert_eq!(body["error"], "storage_error");
        assert!(fake.requests_for("PUT")[0]
            .uri
            .contains("/otterworks-files-chaos-nonexistent/"));
        assert!(fake.requests_for("PutItem").is_empty());
    }

    #[actix_rt::test]
    async fn upload_metadata_failure_is_500() {
        let fake = FakeAws::new();
        fake.respond("PUT", 200, "");
        fake.dynamo_error("PutItem", "InternalServerError");
        let req = upload_req(&[Part::File {
            filename: Some("a"),
            content_type: None,
            data: b"x",
        }])
        .insert_header(("X-User-ID", Uuid::new_v4().to_string()));
        let (status, body) = upload_with(&fake, 1024, &[], req).await;
        assert_eq!(status, StatusCode::INTERNAL_SERVER_ERROR);
        assert_eq!(body["error"], "metadata_error");
        assert_eq!(fake.requests_for("PutItem").len(), 1);
    }

    // -- health --

    #[actix_rt::test]
    async fn health_reports_service_and_version() {
        let resp = health().await;
        let bytes = actix_web::body::to_bytes(resp.into_body()).await.unwrap();
        let body: Value = serde_json::from_slice(&bytes).unwrap();
        assert_eq!(body["status"], "healthy");
        assert_eq!(body["service"], "file-service");
        assert_eq!(body["version"], env!("CARGO_PKG_VERSION"));
    }
}
