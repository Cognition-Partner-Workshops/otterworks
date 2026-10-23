# legacy-share-links

Public share links for documents, from before the document service had its own sharing. A Java 7 servlet WAR that ran on Tomcat 7 on the old application server.

- `GET /share-links/s/<token>` redirects to the shared document.
- `POST /share-links/admin/purge-expired` deletes links that expired more than thirty days ago.

Build with a JDK that still targets Java 7 (JDK 8 to 11): `mvn package`.
