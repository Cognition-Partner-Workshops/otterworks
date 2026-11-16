use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

// ── File Metadata ──────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileMetadata {
    pub id: Uuid,
    pub name: String,
    pub mime_type: String,
    pub size_bytes: u64,
    pub s3_key: String,
    pub folder_id: Option<Uuid>,
    pub owner_id: Uuid,
    pub version: u32,
    pub is_trashed: bool,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Serialize)]
pub struct FileDetailResponse {
    #[serde(flatten)]
    pub file: FileMetadata,
    pub shared_with: Vec<FileShare>,
}

// ── Folder ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Folder {
    pub id: Uuid,
    pub name: String,
    pub parent_id: Option<Uuid>,
    pub owner_id: Uuid,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

// ── File Version ───────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileVersion {
    pub file_id: Uuid,
    pub version: u32,
    pub s3_key: String,
    pub size_bytes: u64,
    pub created_by: Uuid,
    pub created_at: DateTime<Utc>,
}

// ── File Share ─────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileShare {
    pub id: Uuid,
    pub file_id: Uuid,
    pub shared_with: Uuid,
    pub permission: SharePermission,
    pub shared_by: Uuid,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum SharePermission {
    Viewer,
    Editor,
}

impl std::fmt::Display for SharePermission {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            SharePermission::Viewer => write!(f, "viewer"),
            SharePermission::Editor => write!(f, "editor"),
        }
    }
}

impl SharePermission {
    pub fn from_str_value(s: &str) -> Option<Self> {
        match s.to_lowercase().as_str() {
            "viewer" => Some(SharePermission::Viewer),
            "editor" => Some(SharePermission::Editor),
            _ => None,
        }
    }
}

// ── Request / Response Types ───────────────────────────────────────────

#[derive(Debug, Serialize)]
pub struct HealthResponse {
    pub status: String,
    pub service: String,
    pub version: String,
}

#[derive(Debug, Serialize)]
pub struct UploadResponse {
    pub file: FileMetadata,
}

#[derive(Debug, Serialize)]
pub struct DownloadResponse {
    pub url: String,
    pub expires_in_secs: u64,
}

#[derive(Debug, Deserialize)]
pub struct ListFilesQuery {
    pub folder_id: Option<Uuid>,
    pub owner_id: Option<Uuid>,
    pub page: Option<u32>,
    pub page_size: Option<u32>,
    pub include_trashed: Option<bool>,
}

#[derive(Debug, Serialize)]
pub struct ListFilesResponse {
    pub files: Vec<FileMetadata>,
    pub total: usize,
    pub page: u32,
    pub page_size: u32,
}

#[derive(Debug, Serialize)]
pub struct ListVersionsResponse {
    pub versions: Vec<FileVersion>,
}

#[derive(Debug, Deserialize)]
pub struct ListFoldersQuery {
    pub parent_id: Option<Uuid>,
    pub owner_id: Option<Uuid>,
}

#[derive(Debug, Serialize)]
pub struct ListFoldersResponse {
    pub folders: Vec<Folder>,
}

#[derive(Debug, Deserialize)]
pub struct CreateFolderRequest {
    pub name: String,
    pub parent_id: Option<Uuid>,
    pub owner_id: Uuid,
}

#[derive(Debug, Deserialize)]
pub struct UpdateFolderRequest {
    pub name: Option<String>,
    pub parent_id: Option<Uuid>,
}

#[derive(Debug, Deserialize)]
pub struct MoveFileRequest {
    pub folder_id: Option<Uuid>,
}

#[derive(Debug, Deserialize)]
pub struct RenameFileRequest {
    pub name: String,
}

#[derive(Debug, Deserialize)]
pub struct ShareFileRequest {
    pub shared_with: Uuid,
    pub permission: SharePermission,
    pub shared_by: Uuid,
}

#[derive(Debug, Serialize)]
pub struct ShareFileResponse {
    pub share: FileShare,
}

// ── Activity ───────────────────────────────────────────────────────────

#[derive(Debug, Serialize)]
pub struct ActivityItem {
    pub id: String,
    #[serde(rename = "type")]
    pub activity_type: String,
    pub description: String,
    pub actor_name: String,
    pub resource_name: String,
    pub resource_type: String,
    pub resource_id: String,
    pub created_at: String,
}

#[derive(Debug, Deserialize)]
pub struct ActivityQuery {
    pub limit: Option<u32>,
}

#[derive(Debug, Serialize)]
pub struct ActivityResponse {
    pub items: Vec<ActivityItem>,
}

#[cfg(test)]
mod sharing_tests {
    use super::*;

    fn share_request_json(permission: &str) -> serde_json::Value {
        serde_json::json!({
            "shared_with": "22222222-2222-4222-8222-222222222222",
            "permission": permission,
            "shared_by": "11111111-1111-4111-8111-111111111111",
        })
    }

    #[test]
    fn share_request_accepts_viewer_and_editor() {
        for (raw, expected) in [
            ("viewer", SharePermission::Viewer),
            ("editor", SharePermission::Editor),
        ] {
            let req: ShareFileRequest =
                serde_json::from_value(share_request_json(raw)).expect("valid request");
            assert_eq!(req.permission, expected);
        }
    }

    #[test]
    fn share_request_rejects_unknown_permission_levels() {
        for raw in ["owner", "admin", "Viewer", ""] {
            assert!(
                serde_json::from_value::<ShareFileRequest>(share_request_json(raw)).is_err(),
                "permission {raw:?} should be rejected"
            );
        }
    }

    #[test]
    fn share_request_requires_recipient() {
        let body = serde_json::json!({
            "permission": "viewer",
            "shared_by": "11111111-1111-4111-8111-111111111111",
        });
        assert!(serde_json::from_value::<ShareFileRequest>(body).is_err());
    }

    #[test]
    fn share_permission_display_round_trips_through_parser() {
        for perm in [SharePermission::Viewer, SharePermission::Editor] {
            assert_eq!(
                SharePermission::from_str_value(&perm.to_string()),
                Some(perm)
            );
        }
        assert_eq!(
            SharePermission::from_str_value("EDITOR"),
            Some(SharePermission::Editor)
        );
        assert_eq!(SharePermission::from_str_value("commenter"), None);
    }

    #[test]
    fn file_detail_response_flattens_file_and_lists_shares() {
        let now = Utc::now();
        let file_id = Uuid::new_v4();
        let owner = Uuid::new_v4();
        let detail = FileDetailResponse {
            file: FileMetadata {
                id: file_id,
                name: "shared.txt".into(),
                mime_type: "text/plain".into(),
                size_bytes: 2,
                s3_key: format!("files/{owner}/{file_id}"),
                folder_id: None,
                owner_id: owner,
                version: 1,
                is_trashed: false,
                created_at: now,
                updated_at: now,
            },
            shared_with: vec![FileShare {
                id: Uuid::new_v4(),
                file_id,
                shared_with: Uuid::new_v4(),
                permission: SharePermission::Editor,
                shared_by: owner,
                created_at: now,
            }],
        };
        let value = serde_json::to_value(&detail).unwrap();
        assert_eq!(value["id"], file_id.to_string());
        assert_eq!(value["owner_id"], owner.to_string());
        assert_eq!(value["shared_with"][0]["permission"], "editor");
        assert_eq!(value["shared_with"][0]["file_id"], file_id.to_string());
    }
}
