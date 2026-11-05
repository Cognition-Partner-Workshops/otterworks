package com.bank.kyc;

import java.io.InputStream;
import java.io.IOException;
import java.net.URI;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import software.amazon.awssdk.auth.credentials.DefaultCredentialsProvider;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.core.checksums.RequestChecksumCalculation;
import software.amazon.awssdk.http.urlconnection.UrlConnectionHttpClient;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.S3ClientBuilder;
import software.amazon.awssdk.services.s3.S3Configuration;
import software.amazon.awssdk.services.s3.model.*;

@Component
@ConditionalOnProperty(name = "kyc.storage", havingValue = "s3")
public class S3BlobStore implements BlobStore {
    private final S3Client client;
    private final String bucket;

    @Autowired
    public S3BlobStore(@Value("${kyc.s3.bucket}") String bucket,
                       @Value("${kyc.s3.endpoint:}") String endpoint,
                       @Value("${kyc.s3.region:us-east-1}") String region,
                       @Value("${kyc.s3.path-style:false}") boolean pathStyle) {
        this(createClient(endpoint, region, pathStyle), bucket);
    }

    S3BlobStore(S3Client client, String bucket) {
        this.client = client;
        this.bucket = bucket;
    }

    private static S3Client createClient(String endpoint, String region, boolean pathStyle) {
        S3ClientBuilder builder = S3Client.builder()
                .region(Region.of(region))
                .credentialsProvider(DefaultCredentialsProvider.create())
                .httpClientBuilder(UrlConnectionHttpClient.builder())
                .requestChecksumCalculation(RequestChecksumCalculation.WHEN_REQUIRED)
                .serviceConfiguration(S3Configuration.builder()
                        .pathStyleAccessEnabled(pathStyle).chunkedEncodingEnabled(false).build());
        if (!endpoint.isEmpty()) builder.endpointOverride(URI.create(endpoint));
        return builder.build();
    }

    @Override
    public long put(String key, InputStream body, long size) throws IOException {
        Path upload = Files.createTempFile("kyc-upload-", ".tmp");
        try {
            long written = Files.copy(body, upload, StandardCopyOption.REPLACE_EXISTING);
            if (written != size) throw new IOException("multipart size does not match stored bytes");
            client.putObject(PutObjectRequest.builder().bucket(bucket).key(key).contentLength(size).build(),
                    RequestBody.fromFile(upload));
            return written;
        } finally {
            Files.deleteIfExists(upload);
        }
    }

    @Override
    public List<String> list(String customer) {
        String prefix = customer + "/";
        List<String> names = new ArrayList<>();
        String token = null;
        do {
            ListObjectsV2Response page = client.listObjectsV2(ListObjectsV2Request.builder()
                    .bucket(bucket).prefix(prefix).continuationToken(token).build());
            for (S3Object object : page.contents()) {
                names.add(object.key().substring(prefix.length()));
            }
            token = Boolean.TRUE.equals(page.isTruncated()) ? page.nextContinuationToken() : null;
        } while (token != null);
        Collections.sort(names);
        return names;
    }

    @Override
    public boolean healthy() {
        try {
            client.headBucket(HeadBucketRequest.builder().bucket(bucket).build());
            return true;
        } catch (RuntimeException e) {
            return false;
        }
    }
}
