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

// -- Object-level authorization --

/// The authenticated caller, from the `X-User-ID` header the api-gateway sets
/// from validated JWT claims. Object-level handlers refuse to run without one.
fn caller_id(req: &HttpRequest) -> Result<Uuid, ServiceError> {
    req.headers()
        .get("X-User-ID")
        .and_then(|v| v.to_str().ok())
        .and_then(|s| s.trim().parse::<Uuid>().ok())
        .ok_or_else(|| ServiceError::Unauthorized("missing or invalid X-User-ID header".into()))
}

fn ensure_owner(owner_id: &Uuid, caller: &Uuid) -> Result<(), ServiceError> {
    if owner_id == caller {
        Ok(())
    } else {
        Err(ServiceError::Forbidden(
            "caller does not own this resource".into(),
        ))
    }
}

fn parse_id(raw: &str, kind: &str) -> Result<Uuid, ServiceError> {
    raw.parse()
        .map_err(|e| ServiceError::BadRequest(format!("invalid {kind} id: {e}")))
}

/// Load a file the caller owns; any other caller gets 403 before the file is acted on.
async fn owned_file(
    meta: &MetadataClient,
    file_id: &Uuid,
    caller: &Uuid,
) -> Result<FileMetadata, ServiceError> {
    let file = meta.get_file(file_id).await?;
    ensure_owner(&file.owner_id, caller)?;
    Ok(file)
}

/// Load a file the caller owns or has been granted a share on (read-only access).
async fn readable_file(
    meta: &MetadataClient,
    file_id: &Uuid,
    caller: &Uuid,
) -> Result<FileMetadata, ServiceError> {
    let file = meta.get_file(file_id).await?;
    if file.owner_id == *caller || meta.find_existing_share(file_id, caller).await?.is_some() {
        return Ok(file);
    }
    Err(ServiceError::Forbidden(
        "caller does not own and has not been shared this file".into(),
    ))
}

/// Load a folder the caller owns; any other caller gets 403 before the folder is acted on.
async fn owned_folder(
    meta: &MetadataClient,
    folder_id: &Uuid,
    caller: &Uuid,
) -> Result<Folder, ServiceError> {
    let folder = meta.get_folder(folder_id).await?;
    ensure_owner(&folder.owner_id, caller)?;
    Ok(folder)
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
    req: HttpRequest,
    meta: web::Data<MetadataClient>,
    path: web::Path<String>,
) -> Result<HttpResponse, ServiceError> {
    let caller = caller_id(&req)?;
    let file_id = parse_id(&path.into_inner(), "file")?;
    let file = readable_file(&meta, &file_id, &caller).await?;
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
    req: HttpRequest,
    s3: web::Data<S3Client>,
    meta: web::Data<MetadataClient>,
    events: web::Data<EventPublisher>,
    path: web::Path<String>,
) -> Result<HttpResponse, ServiceError> {
    let caller = caller_id(&req)?;
    let file_id = parse_id(&path.into_inner(), "file")?;

    let file = owned_file(&meta, &file_id, &caller).await?;
    meta.delete_file(&file_id).await?;
    s3.delete_object(&file.s3_key).await?;

    let _ = events.file_deleted(&file_id, &file.owner_id).await;

    tracing::info!(file_id = %file_id, "File deleted");
    Ok(HttpResponse::NoContent().finish())
}

pub async fn download_file(
    req: HttpRequest,
    s3: web::Data<S3Client>,
    meta: web::Data<MetadataClient>,
    path: web::Path<String>,
) -> Result<HttpResponse, ServiceError> {
    let caller = caller_id(&req)?;
    let file_id = parse_id(&path.into_inner(), "file")?;

    let file = readable_file(&meta, &file_id, &caller).await?;
    let url = s3.presigned_download_url(&file.s3_key, 3600).await?;

    Ok(HttpResponse::Ok().json(DownloadResponse {
        url,
        expires_in_secs: 3600,
    }))
}

pub async fn move_file(
    req: HttpRequest,
    meta: web::Data<MetadataClient>,
    events: web::Data<EventPublisher>,
    path: web::Path<String>,
    body: web::Json<MoveFileRequest>,
) -> Result<HttpResponse, ServiceError> {
    let caller = caller_id(&req)?;
    let file_id = parse_id(&path.into_inner(), "file")?;

    owned_file(&meta, &file_id, &caller).await?;
    if let Some(folder_id) = &body.folder_id {
        owned_folder(&meta, folder_id, &caller).await?;
    }

    let file = meta.move_file(&file_id, body.folder_id).await?;

    let _ = events
        .file_moved(&file_id, &file.owner_id, body.folder_id.as_ref())
        .await;

    tracing::info!(file_id = %file_id, folder_id = ?body.folder_id, "File moved");
    Ok(HttpResponse::Ok().json(file))
}

pub async fn rename_file(
    req: HttpRequest,
    meta: web::Data<MetadataClient>,
    events: web::Data<EventPublisher>,
    path: web::Path<String>,
    body: web::Json<RenameFileRequest>,
) -> Result<HttpResponse, ServiceError> {
    let caller = caller_id(&req)?;
    let file_id = parse_id(&path.into_inner(), "file")?;

    let name = body.name.trim();
    if name.is_empty() {
        return Err(ServiceError::BadRequest("name cannot be empty".into()));
    }

    owned_file(&meta, &file_id, &caller).await?;

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
    req: HttpRequest,
    meta: web::Data<MetadataClient>,
    path: web::Path<String>,
) -> Result<HttpResponse, ServiceError> {
    let caller = caller_id(&req)?;
    let file_id = parse_id(&path.into_inner(), "file")?;

    readable_file(&meta, &file_id, &caller).await?;
    let versions = meta.list_versions(&file_id).await?;
    Ok(HttpResponse::Ok().json(ListVersionsResponse { versions }))
}

pub async fn trash_file(
    req: HttpRequest,
    meta: web::Data<MetadataClient>,
    events: web::Data<EventPublisher>,
    path: web::Path<String>,
) -> Result<HttpResponse, ServiceError> {
    let caller = caller_id(&req)?;
    let file_id = parse_id(&path.into_inner(), "file")?;

    owned_file(&meta, &file_id, &caller).await?;
    let file = meta.trash_file(&file_id).await?;

    let _ = events.file_trashed(&file_id, &file.owner_id).await;

    tracing::info!(file_id = %file_id, "File trashed");
    Ok(HttpResponse::Ok().json(file))
}

pub async fn restore_file(
    req: HttpRequest,
    meta: web::Data<MetadataClient>,
    events: web::Data<EventPublisher>,
    path: web::Path<String>,
) -> Result<HttpResponse, ServiceError> {
    let caller = caller_id(&req)?;
    let file_id = parse_id(&path.into_inner(), "file")?;

    owned_file(&meta, &file_id, &caller).await?;
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
    req: HttpRequest,
    meta: web::Data<MetadataClient>,
    events: web::Data<EventPublisher>,
    path: web::Path<String>,
    body: web::Json<ShareFileRequest>,
) -> Result<HttpResponse, ServiceError> {
    let caller = caller_id(&req)?;
    let file_id = parse_id(&path.into_inner(), "file")?;

    // Only the owner may grant access, and the grant is attributed to them.
    let file = owned_file(&meta, &file_id, &caller).await?;

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
                shared_by: caller,
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
        shared_by: caller,
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
    req: HttpRequest,
    meta: web::Data<MetadataClient>,
    path: web::Path<(String, String)>,
) -> Result<HttpResponse, ServiceError> {
    let caller = caller_id(&req)?;
    let (file_id_str, user_id_str) = path.into_inner();
    let file_id = parse_id(&file_id_str, "file")?;
    let user_id = parse_id(&user_id_str, "user")?;

    // The owner may revoke any share; a recipient may only drop their own.
    let file = meta.get_file(&file_id).await?;
    if user_id != caller {
        ensure_owner(&file.owner_id, &caller)?;
    }

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
    req: HttpRequest,
    meta: web::Data<MetadataClient>,
    path: web::Path<String>,
) -> Result<HttpResponse, ServiceError> {
    let caller = caller_id(&req)?;
    let folder_id = parse_id(&path.into_inner(), "folder")?;

    let folder = owned_folder(&meta, &folder_id, &caller).await?;
    Ok(HttpResponse::Ok().json(folder))
}

pub async fn update_folder(
    req: HttpRequest,
    meta: web::Data<MetadataClient>,
    path: web::Path<String>,
    body: web::Json<UpdateFolderRequest>,
) -> Result<HttpResponse, ServiceError> {
    let caller = caller_id(&req)?;
    let folder_id = parse_id(&path.into_inner(), "folder")?;

    owned_folder(&meta, &folder_id, &caller).await?;
    if let Some(parent_id) = &body.parent_id {
        owned_folder(&meta, parent_id, &caller).await?;
    }

    let folder = meta
        .update_folder(&folder_id, body.name.clone(), body.parent_id)
        .await?;
    Ok(HttpResponse::Ok().json(folder))
}

pub async fn delete_folder(
    req: HttpRequest,
    meta: web::Data<MetadataClient>,
    path: web::Path<String>,
) -> Result<HttpResponse, ServiceError> {
    let caller = caller_id(&req)?;
    let folder_id = parse_id(&path.into_inner(), "folder")?;

    owned_folder(&meta, &folder_id, &caller).await?;
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

    #[test]
    fn test_ensure_owner() {
        let owner = Uuid::new_v4();
        assert!(ensure_owner(&owner, &owner).is_ok());
        assert!(matches!(
            ensure_owner(&owner, &Uuid::new_v4()),
            Err(ServiceError::Forbidden(_))
        ));
    }

    mod authz {
        use super::*;
        use actix_web::http::StatusCode;
        use actix_web::{test, App};
        use std::sync::{Arc, Mutex};
        use tokio::io::{AsyncReadExt, AsyncWriteExt};
        use tokio::net::TcpListener;

        const GET_ITEM: &str = "dynamodb_20120810.getitem";
        const SCAN: &str = "dynamodb_20120810.scan";

        type Calls = Arc<Mutex<Vec<String>>>;

        fn header(head: &str, name: &str) -> Option<String> {
            head.lines().find_map(|line| {
                let (k, v) = line.split_once(':')?;
                (k.trim() == name).then(|| v.trim().to_string())
            })
        }

        fn item_owned_by(owner: Uuid) -> String {
            let now = Utc::now().to_rfc3339();
            serde_json::json!({
                "Item": {
                    "id": {"S": Uuid::new_v4().to_string()},
                    "name": {"S": "victim.txt"},
                    "mime_type": {"S": "text/plain"},
                    "size_bytes": {"N": "1"},
                    "s3_key": {"S": format!("files/{owner}/victim")},
                    "owner_id": {"S": owner.to_string()},
                    "version": {"N": "1"},
                    "is_trashed": {"BOOL": false},
                    "created_at": {"S": now},
                    "updated_at": {"S": now},
                }
            })
            .to_string()
        }

        fn share_scan(owner: Uuid, grant: Option<Uuid>) -> String {
            let items: Vec<serde_json::Value> = grant
                .map(|recipient| {
                    serde_json::json!({
                        "id": {"S": Uuid::new_v4().to_string()},
                        "file_id": {"S": Uuid::new_v4().to_string()},
                        "shared_with": {"S": recipient.to_string()},
                        "permission": {"S": "viewer"},
                        "shared_by": {"S": owner.to_string()},
                        "created_at": {"S": Utc::now().to_rfc3339()},
                    })
                })
                .into_iter()
                .collect();
            serde_json::json!({"Items": items, "Count": items.len(), "ScannedCount": items.len()})
                .to_string()
        }

        /// A stand-in for DynamoDB/S3 that serves every GetItem as an object owned by
        /// `owner`, every Scan as a share to `grant` (or empty), and records each call.
        async fn fake_aws(owner: Uuid, grant: Option<Uuid>) -> (String, Calls) {
            let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
            let addr = listener.local_addr().unwrap();
            let calls: Calls = Arc::default();
            let recorded = calls.clone();
            tokio::spawn(async move {
                while let Ok((mut sock, _)) = listener.accept().await {
                    let recorded = recorded.clone();
                    tokio::spawn(async move {
                        let mut buf: Vec<u8> = Vec::new();
                        let mut chunk = [0u8; 8192];
                        loop {
                            let header_end = loop {
                                if let Some(pos) = buf.windows(4).position(|w| w == b"\r\n\r\n") {
                                    break pos + 4;
                                }
                                match sock.read(&mut chunk).await {
                                    Ok(0) | Err(_) => return,
                                    Ok(n) => buf.extend_from_slice(&chunk[..n]),
                                }
                            };
                            let head = String::from_utf8_lossy(&buf[..header_end]).to_lowercase();
                            let len: usize = header(&head, "content-length")
                                .and_then(|v| v.parse().ok())
                                .unwrap_or(0);
                            while buf.len() < header_end + len {
                                match sock.read(&mut chunk).await {
                                    Ok(0) | Err(_) => return,
                                    Ok(n) => buf.extend_from_slice(&chunk[..n]),
                                }
                            }
                            buf.drain(..header_end + len);
                            let call = header(&head, "x-amz-target").unwrap_or_else(|| {
                                head.lines().next().unwrap_or_default().to_string()
                            });
                            recorded.lock().unwrap().push(call.clone());
                            let body = match call.as_str() {
                                GET_ITEM => item_owned_by(owner),
                                SCAN => share_scan(owner, grant),
                                _ => "{}".to_string(),
                            };
                            let resp = format!(
                                "HTTP/1.1 200 OK\r\nContent-Type: application/x-amz-json-1.0\r\nContent-Length: {}\r\n\r\n{}",
                                body.len(),
                                body
                            );
                            if sock.write_all(resp.as_bytes()).await.is_err() {
                                return;
                            }
                        }
                    });
                }
            });
            (format!("http://{addr}"), calls)
        }

        struct Harness {
            meta: web::Data<MetadataClient>,
            s3: web::Data<S3Client>,
            events: web::Data<EventPublisher>,
            calls: Calls,
        }

        async fn harness(owner: Uuid) -> Harness {
            harness_with_grant(owner, None).await
        }

        async fn harness_with_grant(owner: Uuid, grant: Option<Uuid>) -> Harness {
            let (endpoint, calls) = fake_aws(owner, grant).await;
            let creds =
                aws_sdk_dynamodb::config::Credentials::new("test", "test", None, None, "test");
            let dynamo = aws_sdk_dynamodb::Config::builder()
                .behavior_version(aws_sdk_dynamodb::config::BehaviorVersion::latest())
                .region(aws_sdk_dynamodb::config::Region::new("us-east-1"))
                .credentials_provider(creds.clone())
                .endpoint_url(&endpoint)
                .build();
            let s3 = aws_sdk_s3::Config::builder()
                .behavior_version(aws_sdk_s3::config::BehaviorVersion::latest())
                .region(aws_sdk_s3::config::Region::new("us-east-1"))
                .credentials_provider(creds)
                .endpoint_url(&endpoint)
                .force_path_style(true)
                .build();
            let aws = crate::config::AwsConfig {
                region: "us-east-1".into(),
                endpoint_url: Some(endpoint),
                s3_bucket: "otterworks-files".into(),
                dynamodb_table: "files".into(),
                dynamodb_folders_table: "folders".into(),
                dynamodb_versions_table: "versions".into(),
                dynamodb_shares_table: "shares".into(),
            };
            let events =
                EventPublisher::new(&crate::config::SnsConfig { topic_arn: None }, &aws).await;
            Harness {
                meta: web::Data::new(MetadataClient {
                    client: aws_sdk_dynamodb::Client::from_conf(dynamo),
                    files_table: aws.dynamodb_table,
                    folders_table: aws.dynamodb_folders_table,
                    versions_table: aws.dynamodb_versions_table,
                    shares_table: aws.dynamodb_shares_table,
                }),
                s3: web::Data::new(S3Client {
                    client: aws_sdk_s3::Client::from_conf(s3),
                    bucket: aws.s3_bucket,
                }),
                events: web::Data::new(events),
                calls,
            }
        }

        impl Harness {
            async fn send(&self, req: test::TestRequest) -> (StatusCode, serde_json::Value) {
                let app = test::init_service(
                    App::new()
                        .app_data(self.meta.clone())
                        .app_data(self.s3.clone())
                        .app_data(self.events.clone())
                        .service(
                            web::scope("/api/v1/files")
                                .route("/{file_id}", web::get().to(get_file_metadata))
                                .route("/{file_id}", web::delete().to(delete_file))
                                .route("/{file_id}/download", web::get().to(download_file))
                                .route("/{file_id}/move", web::put().to(move_file))
                                .route("/{file_id}/rename", web::patch().to(rename_file))
                                .route("/{file_id}/versions", web::get().to(list_versions))
                                .route("/{file_id}/trash", web::post().to(trash_file))
                                .route("/{file_id}/restore", web::post().to(restore_file))
                                .route("/{file_id}/share", web::post().to(share_file))
                                .route(
                                    "/{file_id}/share/{user_id}",
                                    web::delete().to(remove_share),
                                ),
                        )
                        .service(
                            web::scope("/api/v1/folders")
                                .route("/{folder_id}", web::get().to(get_folder))
                                .route("/{folder_id}", web::put().to(update_folder))
                                .route("/{folder_id}", web::delete().to(delete_folder)),
                        ),
                )
                .await;
                let resp = test::call_service(&app, req.to_request()).await;
                let status = resp.status();
                let body = test::read_body(resp).await;
                (status, serde_json::from_slice(&body).unwrap_or_default())
            }

            fn take_calls(&self) -> Vec<String> {
                std::mem::take(&mut *self.calls.lock().unwrap())
            }
        }

        fn object_requests(id: Uuid) -> Vec<test::TestRequest> {
            let f = format!("/api/v1/files/{id}");
            let d = format!("/api/v1/folders/{id}");
            let other = Uuid::new_v4();
            vec![
                test::TestRequest::get().uri(&f),
                test::TestRequest::delete().uri(&f),
                test::TestRequest::get().uri(&format!("{f}/download")),
                test::TestRequest::put()
                    .uri(&format!("{f}/move"))
                    .set_json(serde_json::json!({"folder_id": null})),
                test::TestRequest::patch()
                    .uri(&format!("{f}/rename"))
                    .set_json(serde_json::json!({"name": "pwned"})),
                test::TestRequest::get().uri(&format!("{f}/versions")),
                test::TestRequest::post().uri(&format!("{f}/trash")),
                test::TestRequest::post().uri(&format!("{f}/restore")),
                test::TestRequest::post().uri(&format!("{f}/share")).set_json(
                    serde_json::json!({"shared_with": other, "permission": "editor", "shared_by": other}),
                ),
                test::TestRequest::delete().uri(&format!("{f}/share/{other}")),
                test::TestRequest::get().uri(&d),
                test::TestRequest::put()
                    .uri(&d)
                    .set_json(serde_json::json!({"name": "pwned"})),
                test::TestRequest::delete().uri(&d),
            ]
        }

        #[actix_rt::test]
        async fn missing_or_invalid_caller_is_rejected_before_any_aws_call() {
            let h = harness(Uuid::new_v4()).await;
            for (i, req) in object_requests(Uuid::new_v4()).into_iter().enumerate() {
                let (status, _) = h.send(req).await;
                assert_eq!(
                    status,
                    StatusCode::UNAUTHORIZED,
                    "request #{i} without X-User-ID"
                );
            }
            for req in object_requests(Uuid::new_v4()) {
                let (status, _) = h.send(req.insert_header(("X-User-ID", "not-a-uuid"))).await;
                assert_eq!(status, StatusCode::UNAUTHORIZED);
            }
            assert!(h.take_calls().is_empty());
        }

        #[actix_rt::test]
        async fn non_owner_is_forbidden_before_acting_on_the_object() {
            let owner = Uuid::new_v4();
            let attacker = Uuid::new_v4();
            let h = harness(owner).await;
            for (i, req) in object_requests(Uuid::new_v4()).into_iter().enumerate() {
                let (status, _) = h
                    .send(req.insert_header(("X-User-ID", attacker.to_string())))
                    .await;
                assert_eq!(status, StatusCode::FORBIDDEN, "request #{i} as non-owner");
                // Only the ownership lookup (plus the share-grant lookup for reads)
                // may reach AWS: no update, delete, put, or S3 call.
                for call in h.take_calls() {
                    assert!(call == GET_ITEM || call == SCAN, "request #{i} made {call}");
                }
            }
        }

        #[actix_rt::test]
        async fn owner_can_read_and_download_their_file() {
            let owner = Uuid::new_v4();
            let h = harness(owner).await;
            let id = Uuid::new_v4();
            let (status, _) = h
                .send(
                    test::TestRequest::get()
                        .uri(&format!("/api/v1/files/{id}"))
                        .insert_header(("X-User-ID", owner.to_string())),
                )
                .await;
            assert_eq!(status, StatusCode::OK);
            let (status, body) = h
                .send(
                    test::TestRequest::get()
                        .uri(&format!("/api/v1/files/{id}/download"))
                        .insert_header(("X-User-ID", owner.to_string())),
                )
                .await;
            assert_eq!(status, StatusCode::OK);
            assert!(body["url"].as_str().unwrap().contains(&owner.to_string()));
        }

        #[actix_rt::test]
        async fn share_recipient_may_read_but_not_act_as_owner() {
            let owner = Uuid::new_v4();
            let recipient = Uuid::new_v4();
            let h = harness_with_grant(owner, Some(recipient)).await;
            let f = format!("/api/v1/files/{}", Uuid::new_v4());
            let as_recipient =
                |req: test::TestRequest| req.insert_header(("X-User-ID", recipient.to_string()));
            for uri in [f.clone(), format!("{f}/download"), format!("{f}/versions")] {
                let (status, _) = h
                    .send(as_recipient(test::TestRequest::get().uri(&uri)))
                    .await;
                assert_eq!(status, StatusCode::OK, "recipient GET {uri}");
            }
            let owner_only = [
                test::TestRequest::delete().uri(&f),
                test::TestRequest::post()
                    .uri(&format!("{f}/share"))
                    .set_json(
                        serde_json::json!({"shared_with": recipient, "permission": "editor"}),
                    ),
                test::TestRequest::patch()
                    .uri(&format!("{f}/rename"))
                    .set_json(serde_json::json!({"name": "pwned"})),
                test::TestRequest::post().uri(&format!("{f}/trash")),
            ];
            h.take_calls();
            for (i, req) in owner_only.into_iter().enumerate() {
                let (status, _) = h.send(as_recipient(req)).await;
                assert_eq!(status, StatusCode::FORBIDDEN, "owner-only request #{i}");
                for call in h.take_calls() {
                    assert!(call == GET_ITEM || call == SCAN, "request #{i} made {call}");
                }
            }
        }

        #[actix_rt::test]
        async fn share_is_attributed_to_the_caller_not_the_body() {
            let owner = Uuid::new_v4();
            let h = harness(owner).await;
            let forged = Uuid::new_v4();
            let (status, body) = h
                .send(
                    test::TestRequest::post()
                        .uri(&format!("/api/v1/files/{}/share", Uuid::new_v4()))
                        .insert_header(("X-User-ID", owner.to_string()))
                        .set_json(serde_json::json!({
                            "shared_with": Uuid::new_v4(),
                            "permission": "viewer",
                            "shared_by": forged,
                        })),
                )
                .await;
            assert_eq!(status, StatusCode::CREATED);
            assert_eq!(body["share"]["shared_by"], owner.to_string());
        }

        #[actix_rt::test]
        async fn recipient_may_remove_only_their_own_share() {
            let owner = Uuid::new_v4();
            let recipient = Uuid::new_v4();
            let h = harness(owner).await;
            let file = Uuid::new_v4();
            let (status, _) = h
                .send(
                    test::TestRequest::delete()
                        .uri(&format!("/api/v1/files/{file}/share/{}", Uuid::new_v4()))
                        .insert_header(("X-User-ID", recipient.to_string())),
                )
                .await;
            assert_eq!(status, StatusCode::FORBIDDEN);
            // Their own grant passes authorization; the fake has no share rows, so 404.
            let (status, _) = h
                .send(
                    test::TestRequest::delete()
                        .uri(&format!("/api/v1/files/{file}/share/{recipient}"))
                        .insert_header(("X-User-ID", recipient.to_string())),
                )
                .await;
            assert_eq!(status, StatusCode::NOT_FOUND);
        }
    }
}
