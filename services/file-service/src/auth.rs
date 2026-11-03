//! Caller identity for every `/api/v1` route.
//!
//! Identity comes only from a bearer JWT this service verifies itself with the
//! same HMAC key auth-service signs with. `X-User-ID` and any `owner_id` in a
//! query or body are never trusted: the service is reachable without passing
//! through the gateway (compose ports, in-cluster callers), so a header proves
//! nothing about who sent it.

use std::collections::HashSet;

use actix_web::dev::Payload;
use actix_web::{web, FromRequest, HttpRequest};
use futures_util::future::{ready, Ready};
use jsonwebtoken::{decode, Algorithm, DecodingKey, Validation};
use serde::Deserialize;
use uuid::Uuid;

use crate::config::AppConfig;
use crate::errors::ServiceError;

#[derive(Debug, Deserialize)]
struct Claims {
    sub: Option<String>,
    user_id: Option<String>,
    #[serde(rename = "type")]
    token_type: Option<String>,
}

/// The verified caller. Extracting it rejects the request with 401 unless it
/// carries a valid, unexpired access token.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct AuthenticatedUser {
    pub id: Uuid,
}

impl FromRequest for AuthenticatedUser {
    type Error = ServiceError;
    type Future = Ready<Result<Self, Self::Error>>;

    fn from_request(req: &HttpRequest, _payload: &mut Payload) -> Self::Future {
        ready(authenticate(req))
    }
}

fn authenticate(req: &HttpRequest) -> Result<AuthenticatedUser, ServiceError> {
    let config = req
        .app_data::<web::Data<AppConfig>>()
        .ok_or_else(|| ServiceError::Internal("auth configuration missing".into()))?;
    let token = bearer_token(req)
        .ok_or_else(|| ServiceError::Unauthorized("missing bearer token".into()))?;
    verify_token(token, &config.auth.jwt_secrets)
}

fn bearer_token(req: &HttpRequest) -> Option<&str> {
    let header = req.headers().get("Authorization")?.to_str().ok()?;
    let (scheme, token) = header.split_once(' ')?;
    let token = token.trim();
    (scheme.eq_ignore_ascii_case("bearer") && !token.is_empty()).then_some(token)
}

pub fn verify_token(token: &str, secrets: &[String]) -> Result<AuthenticatedUser, ServiceError> {
    let mut validation = Validation::new(Algorithm::HS256);
    validation.algorithms = vec![Algorithm::HS256, Algorithm::HS384, Algorithm::HS512];
    validation.required_spec_claims = HashSet::from(["exp".to_string()]);

    let claims = secrets
        .iter()
        .find_map(|secret| {
            decode::<Claims>(
                token,
                &DecodingKey::from_secret(secret.as_bytes()),
                &validation,
            )
            .ok()
        })
        .ok_or_else(|| ServiceError::Unauthorized("invalid or expired token".into()))?
        .claims;

    if claims.token_type.as_deref() == Some("refresh") {
        return Err(ServiceError::Unauthorized(
            "refresh token cannot be used as an access token".into(),
        ));
    }

    let id = claims
        .sub
        .filter(|s| !s.is_empty())
        .or(claims.user_id)
        .and_then(|s| s.parse::<Uuid>().ok())
        .ok_or_else(|| ServiceError::Unauthorized("token has no user id".into()))?;

    Ok(AuthenticatedUser { id })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::{AuthConfig, AwsConfig, ServerConfig, SnsConfig};
    use actix_web::test::{call_service, init_service, read_body, TestRequest};
    use actix_web::{App, HttpResponse};
    use jsonwebtoken::{encode, EncodingKey, Header};
    use serde_json::json;

    const SECRET: &str = "file-service-test-secret";

    fn token(alg: Algorithm, secret: &str, claims: serde_json::Value) -> String {
        encode(
            &Header::new(alg),
            &claims,
            &EncodingKey::from_secret(secret.as_bytes()),
        )
        .unwrap()
    }

    fn exp(offset_secs: i64) -> i64 {
        chrono::Utc::now().timestamp() + offset_secs
    }

    fn secrets() -> Vec<String> {
        vec![SECRET.to_string()]
    }

    #[test]
    fn accepts_access_token_signed_with_service_secret() {
        let user = Uuid::new_v4();
        for alg in [Algorithm::HS256, Algorithm::HS384, Algorithm::HS512] {
            let t = token(
                alg,
                SECRET,
                json!({"sub": user, "type": "access", "exp": exp(600)}),
            );
            assert_eq!(verify_token(&t, &secrets()).unwrap().id, user);
        }
    }

    #[test]
    fn accepts_user_id_claim_and_peer_secret() {
        let user = Uuid::new_v4();
        let t = token(
            Algorithm::HS256,
            "peer",
            json!({"user_id": user, "exp": exp(600)}),
        );
        let keys = vec![SECRET.to_string(), "peer".to_string()];
        assert_eq!(verify_token(&t, &keys).unwrap().id, user);
    }

    #[test]
    fn rejects_forged_expired_refresh_and_unconfigured() {
        let user = Uuid::new_v4();
        let forged = token(
            Algorithm::HS256,
            "attacker",
            json!({"sub": user, "exp": exp(600)}),
        );
        let expired = token(
            Algorithm::HS256,
            SECRET,
            json!({"sub": user, "exp": exp(-3600)}),
        );
        let refresh = token(
            Algorithm::HS256,
            SECRET,
            json!({"sub": user, "type": "refresh", "exp": exp(600)}),
        );
        let no_exp = token(Algorithm::HS256, SECRET, json!({"sub": user}));
        let no_user = token(Algorithm::HS256, SECRET, json!({"exp": exp(600)}));
        for t in [&forged, &expired, &refresh, &no_exp, &no_user] {
            assert!(matches!(
                verify_token(t, &secrets()),
                Err(ServiceError::Unauthorized(_))
            ));
        }
        let valid = token(
            Algorithm::HS256,
            SECRET,
            json!({"sub": user, "exp": exp(600)}),
        );
        assert!(verify_token(&valid, &[]).is_err());
    }

    fn app_config() -> AppConfig {
        AppConfig {
            server: ServerConfig {
                port: 0,
                max_upload_bytes: 0,
            },
            aws: AwsConfig {
                region: String::new(),
                endpoint_url: None,
                s3_bucket: String::new(),
                dynamodb_table: String::new(),
                dynamodb_folders_table: String::new(),
                dynamodb_versions_table: String::new(),
                dynamodb_shares_table: String::new(),
            },
            sns: SnsConfig { topic_arn: None },
            auth: AuthConfig {
                jwt_secrets: secrets(),
            },
        }
    }

    async fn whoami(user: AuthenticatedUser) -> HttpResponse {
        HttpResponse::Ok().body(user.id.to_string())
    }

    #[actix_rt::test]
    async fn forged_x_user_id_without_token_gets_401() {
        let app = init_service(
            App::new()
                .app_data(web::Data::new(app_config()))
                .route("/api/v1/files", web::get().to(whoami)),
        )
        .await;

        let victim = Uuid::new_v4();
        let req = TestRequest::get()
            .uri(&format!("/api/v1/files?owner_id={victim}"))
            .insert_header(("X-User-ID", victim.to_string()))
            .to_request();
        assert_eq!(call_service(&app, req).await.status(), 401);

        let caller = Uuid::new_v4();
        let t = token(
            Algorithm::HS256,
            SECRET,
            json!({"sub": caller, "exp": exp(600)}),
        );
        let req = TestRequest::get()
            .uri("/api/v1/files")
            .insert_header(("X-User-ID", victim.to_string()))
            .insert_header(("Authorization", format!("Bearer {t}")))
            .to_request();
        let resp = call_service(&app, req).await;
        assert_eq!(resp.status(), 200);
        assert_eq!(read_body(resp).await, caller.to_string());
    }
}
