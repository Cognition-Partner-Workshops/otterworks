//! Gateway identity attestation.
//!
//! The api-gateway validates the caller's JWT and forwards the user id as
//! `X-User-ID`, together with `X-Gateway-Signature` =
//! `hex(HMAC-SHA256(INTERNAL_AUTH_SECRET, X-User-ID))`. Handlers that need the
//! caller take a [`GatewayIdentity`] extractor, which only yields a user id when
//! that signature verifies. A bare `X-User-ID` (as any caller reaching this
//! service without the gateway could send) is rejected with 401, and so is
//! every identity header when the secret is not configured.

use std::future::{ready, Ready};

use actix_web::{dev::Payload, web, FromRequest, HttpRequest};
use hmac::{Hmac, Mac};
use sha2::Sha256;
use uuid::Uuid;

use crate::config::AppConfig;
use crate::errors::ServiceError;

pub const USER_ID_HEADER: &str = "X-User-ID";
pub const SIGNATURE_HEADER: &str = "X-Gateway-Signature";

type HmacSha256 = Hmac<Sha256>;

/// The authenticated caller, as attested by the api-gateway.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct GatewayIdentity {
    pub user_id: Uuid,
}

/// Signature the gateway attaches to `user_id` under `secret` (hex, lowercase).
pub fn sign_identity(secret: &str, user_id: &str) -> String {
    let mut mac = HmacSha256::new_from_slice(secret.as_bytes()).expect("HMAC accepts any key size");
    mac.update(user_id.as_bytes());
    hex::encode(mac.finalize().into_bytes())
}

/// Constant-time check that `signature` attests `user_id` under `secret`.
pub fn verify_identity(secret: &str, user_id: &str, signature: &str) -> bool {
    if secret.is_empty() || user_id.is_empty() || signature.is_empty() {
        return false;
    }
    let Ok(expected) = hex::decode(signature.trim()) else {
        return false;
    };
    let mut mac = HmacSha256::new_from_slice(secret.as_bytes()).expect("HMAC accepts any key size");
    mac.update(user_id.as_bytes());
    mac.verify_slice(&expected).is_ok()
}

fn header_str<'a>(req: &'a HttpRequest, name: &str) -> &'a str {
    req.headers()
        .get(name)
        .and_then(|v| v.to_str().ok())
        .map(str::trim)
        .unwrap_or("")
}

impl FromRequest for GatewayIdentity {
    type Error = ServiceError;
    type Future = Ready<Result<Self, Self::Error>>;

    fn from_request(req: &HttpRequest, _payload: &mut Payload) -> Self::Future {
        ready(extract(req))
    }
}

fn extract(req: &HttpRequest) -> Result<GatewayIdentity, ServiceError> {
    let secret = req
        .app_data::<web::Data<AppConfig>>()
        .map(|c| c.auth.internal_auth_secret.as_str())
        .unwrap_or("");
    let user_id = header_str(req, USER_ID_HEADER);
    let signature = header_str(req, SIGNATURE_HEADER);

    if !verify_identity(secret, user_id, signature) {
        tracing::warn!(
            has_user_id = !user_id.is_empty(),
            has_signature = !signature.is_empty(),
            path = %req.path(),
            "rejected request without a gateway-attested identity"
        );
        return Err(ServiceError::Unauthorized(
            "missing or invalid gateway identity".into(),
        ));
    }

    let user_id = user_id
        .parse::<Uuid>()
        .map_err(|e| ServiceError::BadRequest(format!("invalid X-User-ID: {e}")))?;
    Ok(GatewayIdentity { user_id })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::{AuthConfig, AwsConfig, ServerConfig, SnsConfig};
    use actix_web::test::TestRequest;

    const SECRET: &str = "test-internal-auth-secret";
    const VICTIM: &str = "62665f61-e96b-4190-922b-0c007916872c";

    fn config(secret: &str) -> web::Data<AppConfig> {
        web::Data::new(AppConfig {
            server: ServerConfig {
                port: 8082,
                max_upload_bytes: 1,
            },
            aws: AwsConfig {
                region: "us-east-1".into(),
                endpoint_url: None,
                s3_bucket: "b".into(),
                dynamodb_table: "t".into(),
                dynamodb_folders_table: "f".into(),
                dynamodb_versions_table: "v".into(),
                dynamodb_shares_table: "s".into(),
            },
            sns: SnsConfig { topic_arn: None },
            auth: AuthConfig {
                internal_auth_secret: secret.into(),
            },
        })
    }

    fn extract_with(
        secret: &str,
        headers: &[(&str, String)],
    ) -> Result<GatewayIdentity, ServiceError> {
        let mut req = TestRequest::get()
            .uri("/api/v1/files")
            .app_data(config(secret));
        for (name, value) in headers {
            req = req.insert_header((*name, value.as_str()));
        }
        extract(&req.to_http_request())
    }

    fn status(err: ServiceError) -> actix_web::http::StatusCode {
        actix_web::ResponseError::error_response(&err).status()
    }

    #[test]
    fn sign_verify_round_trip() {
        let sig = sign_identity(SECRET, VICTIM);
        assert!(verify_identity(SECRET, VICTIM, &sig));
        assert!(!verify_identity("other-key", VICTIM, &sig));
        assert!(!verify_identity(SECRET, "other-user", &sig));
        assert!(!verify_identity(SECRET, VICTIM, "not-hex"));
        assert!(!verify_identity("", VICTIM, &sig));
    }

    #[test]
    fn no_headers_is_unauthorized() {
        let err = extract_with(SECRET, &[]).unwrap_err();
        assert_eq!(status(err), actix_web::http::StatusCode::UNAUTHORIZED);
    }

    #[test]
    fn bare_x_user_id_is_unauthorized() {
        // The previously exploitable request: identity asserted by the client alone.
        let err = extract_with(SECRET, &[(USER_ID_HEADER, VICTIM.into())]).unwrap_err();
        assert_eq!(status(err), actix_web::http::StatusCode::UNAUTHORIZED);
    }

    #[test]
    fn signature_under_another_key_is_unauthorized() {
        let headers = [
            (USER_ID_HEADER, VICTIM.to_string()),
            (SIGNATURE_HEADER, sign_identity("attacker-key", VICTIM)),
        ];
        let err = extract_with(SECRET, &headers).unwrap_err();
        assert_eq!(status(err), actix_web::http::StatusCode::UNAUTHORIZED);
    }

    #[test]
    fn signature_for_another_user_is_unauthorized() {
        let headers = [
            (USER_ID_HEADER, VICTIM.to_string()),
            (
                SIGNATURE_HEADER,
                sign_identity(SECRET, "00000000-0000-4000-8000-000000000001"),
            ),
        ];
        let err = extract_with(SECRET, &headers).unwrap_err();
        assert_eq!(status(err), actix_web::http::StatusCode::UNAUTHORIZED);
    }

    #[test]
    fn unconfigured_secret_fails_closed() {
        let headers = [
            (USER_ID_HEADER, VICTIM.to_string()),
            (SIGNATURE_HEADER, sign_identity("", VICTIM)),
        ];
        let err = extract_with("", &headers).unwrap_err();
        assert_eq!(status(err), actix_web::http::StatusCode::UNAUTHORIZED);
    }

    #[test]
    fn gateway_signed_identity_is_accepted() {
        let headers = [
            (USER_ID_HEADER, VICTIM.to_string()),
            (SIGNATURE_HEADER, sign_identity(SECRET, VICTIM)),
        ];
        let identity = extract_with(SECRET, &headers).unwrap();
        assert_eq!(identity.user_id, VICTIM.parse::<Uuid>().unwrap());
    }

    #[test]
    fn attested_but_malformed_user_id_is_bad_request() {
        let headers = [
            (USER_ID_HEADER, "not-a-uuid".to_string()),
            (SIGNATURE_HEADER, sign_identity(SECRET, "not-a-uuid")),
        ];
        let err = extract_with(SECRET, &headers).unwrap_err();
        assert_eq!(status(err), actix_web::http::StatusCode::BAD_REQUEST);
    }
}
