use actix_web::{HttpResponse, ResponseError};
use std::fmt;

#[derive(Debug, thiserror::Error)]
pub enum ServiceError {
    #[error("File not found: {0}")]
    FileNotFound(String),

    #[error("Folder not found: {0}")]
    FolderNotFound(String),

    #[error("Version not found: {0}")]
    VersionNotFound(String),

    #[error("Share not found: {0}")]
    ShareNotFound(String),

    #[error("Bad request: {0}")]
    BadRequest(String),

    #[error("File too large: max {max_bytes} bytes, got {actual_bytes} bytes")]
    FileTooLarge { max_bytes: u64, actual_bytes: u64 },

    #[error("Unauthorized: {0}")]
    Unauthorized(String),

    #[error("Forbidden: {0}")]
    Forbidden(String),

    #[error("S3 error: {0}")]
    S3Error(String),

    #[error("DynamoDB error: {0}")]
    DynamoError(String),

    #[error("SNS error: {0}")]
    SnsError(String),

    #[error("Internal error: {0}")]
    Internal(String),
}

impl ResponseError for ServiceError {
    fn error_response(&self) -> HttpResponse {
        let (status, error_type) = match self {
            ServiceError::FileNotFound(_) => {
                (actix_web::http::StatusCode::NOT_FOUND, "file_not_found")
            }
            ServiceError::FolderNotFound(_) => {
                (actix_web::http::StatusCode::NOT_FOUND, "folder_not_found")
            }
            ServiceError::VersionNotFound(_) => {
                (actix_web::http::StatusCode::NOT_FOUND, "version_not_found")
            }
            ServiceError::ShareNotFound(_) => {
                (actix_web::http::StatusCode::NOT_FOUND, "share_not_found")
            }
            ServiceError::BadRequest(_) => {
                (actix_web::http::StatusCode::BAD_REQUEST, "bad_request")
            }
            ServiceError::FileTooLarge { .. } => (
                actix_web::http::StatusCode::PAYLOAD_TOO_LARGE,
                "file_too_large",
            ),
            ServiceError::Unauthorized(_) => {
                (actix_web::http::StatusCode::UNAUTHORIZED, "unauthorized")
            }
            ServiceError::Forbidden(_) => (actix_web::http::StatusCode::FORBIDDEN, "forbidden"),
            ServiceError::S3Error(_) => (
                actix_web::http::StatusCode::INTERNAL_SERVER_ERROR,
                "storage_error",
            ),
            ServiceError::DynamoError(_) => (
                actix_web::http::StatusCode::INTERNAL_SERVER_ERROR,
                "metadata_error",
            ),
            ServiceError::SnsError(_) => (
                actix_web::http::StatusCode::INTERNAL_SERVER_ERROR,
                "event_error",
            ),
            ServiceError::Internal(_) => (
                actix_web::http::StatusCode::INTERNAL_SERVER_ERROR,
                "internal_error",
            ),
        };

        HttpResponse::build(status).json(ErrorResponse {
            error: error_type.to_string(),
            message: self.to_string(),
        })
    }
}

#[derive(Debug, serde::Serialize)]
pub struct ErrorResponse {
    pub error: String,
    pub message: String,
}

impl fmt::Display for ErrorResponse {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}: {}", self.error, self.message)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use actix_web::body::MessageBody;
    use actix_web::http::StatusCode;

    fn render(err: &ServiceError) -> (StatusCode, serde_json::Value) {
        let resp = err.error_response();
        let status = resp.status();
        let bytes = resp
            .into_body()
            .try_into_bytes()
            .expect("error body is in-memory JSON");
        (status, serde_json::from_slice(&bytes).unwrap())
    }

    #[test]
    fn maps_every_variant_to_status_and_error_type() {
        let cases = [
            (
                ServiceError::FileNotFound("f".into()),
                StatusCode::NOT_FOUND,
                "file_not_found",
            ),
            (
                ServiceError::FolderNotFound("d".into()),
                StatusCode::NOT_FOUND,
                "folder_not_found",
            ),
            (
                ServiceError::VersionNotFound("v".into()),
                StatusCode::NOT_FOUND,
                "version_not_found",
            ),
            (
                ServiceError::ShareNotFound("s".into()),
                StatusCode::NOT_FOUND,
                "share_not_found",
            ),
            (
                ServiceError::BadRequest("b".into()),
                StatusCode::BAD_REQUEST,
                "bad_request",
            ),
            (
                ServiceError::FileTooLarge {
                    max_bytes: 10,
                    actual_bytes: 11,
                },
                StatusCode::PAYLOAD_TOO_LARGE,
                "file_too_large",
            ),
            (
                ServiceError::Unauthorized("u".into()),
                StatusCode::UNAUTHORIZED,
                "unauthorized",
            ),
            (
                ServiceError::Forbidden("x".into()),
                StatusCode::FORBIDDEN,
                "forbidden",
            ),
            (
                ServiceError::S3Error("s3".into()),
                StatusCode::INTERNAL_SERVER_ERROR,
                "storage_error",
            ),
            (
                ServiceError::DynamoError("ddb".into()),
                StatusCode::INTERNAL_SERVER_ERROR,
                "metadata_error",
            ),
            (
                ServiceError::SnsError("sns".into()),
                StatusCode::INTERNAL_SERVER_ERROR,
                "event_error",
            ),
            (
                ServiceError::Internal("i".into()),
                StatusCode::INTERNAL_SERVER_ERROR,
                "internal_error",
            ),
        ];

        for (err, status, error_type) in cases {
            let (got_status, body) = render(&err);
            assert_eq!(got_status, status, "{err:?}");
            assert_eq!(body["error"], error_type, "{err:?}");
            assert_eq!(body["message"], err.to_string(), "{err:?}");
        }
    }

    #[test]
    fn display_messages_include_context() {
        assert_eq!(
            ServiceError::FileNotFound("abc".into()).to_string(),
            "File not found: abc"
        );
        assert_eq!(
            ServiceError::BadRequest("name cannot be empty".into()).to_string(),
            "Bad request: name cannot be empty"
        );
        assert_eq!(
            ServiceError::FileTooLarge {
                max_bytes: 100,
                actual_bytes: 150
            }
            .to_string(),
            "File too large: max 100 bytes, got 150 bytes"
        );
        assert_eq!(
            ServiceError::S3Error("upload failed: boom".into()).to_string(),
            "S3 error: upload failed: boom"
        );
    }

    #[test]
    fn error_body_has_only_error_and_message_fields() {
        let (_, body) = render(&ServiceError::Forbidden("nope".into()));
        let obj = body.as_object().unwrap();
        assert_eq!(obj.len(), 2);
        assert!(obj.contains_key("error"));
        assert!(obj.contains_key("message"));
    }

    #[test]
    fn error_response_content_type_is_json() {
        let resp = ServiceError::Internal("x".into()).error_response();
        assert_eq!(
            resp.headers().get("content-type").unwrap(),
            "application/json"
        );
    }

    #[test]
    fn error_response_struct_display() {
        let e = ErrorResponse {
            error: "bad_request".into(),
            message: "Bad request: x".into(),
        };
        assert_eq!(e.to_string(), "bad_request: Bad request: x");
    }
}
