package com.bank.kyc;

import java.net.URI;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import software.amazon.awssdk.http.urlconnection.UrlConnectionHttpClient;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.S3ClientBuilder;

@Configuration
public class StoreConfig {

    /**
     * kyc.store=s3 keeps documents in a bucket (credentials from the default AWS chain: workload
     * identity, or AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY from a secret); kyc.store=fs keeps them
     * under kyc.upload-dir.
     */
    @Bean
    public DocumentStore documentStore(@Value("${kyc.store}") String store,
                                       @Value("${kyc.upload-dir}") String uploadDir,
                                       @Value("${kyc.s3.bucket}") String bucket,
                                       @Value("${kyc.s3.prefix}") String prefix,
                                       @Value("${kyc.s3.region}") String region,
                                       @Value("${kyc.s3.endpoint}") String endpoint,
                                       @Value("${kyc.s3.path-style}") boolean pathStyle,
                                       @Value("${kyc.s3.create-bucket}") boolean createBucket) {
        if ("fs".equals(store)) return new DocumentStore(new FileBackend(uploadDir));
        if (!"s3".equals(store)) throw new IllegalStateException("kyc.store must be s3 or fs, not " + store);
        if (bucket.isBlank()) throw new IllegalStateException("KYC_S3_BUCKET is required when KYC_STORE=s3");
        S3ClientBuilder b = S3Client.builder()
                .httpClient(UrlConnectionHttpClient.create())
                .region(Region.of(region))
                .forcePathStyle(pathStyle);
        if (!endpoint.isBlank()) b.endpointOverride(URI.create(endpoint));
        return new DocumentStore(new S3Backend(b.build(), bucket, prefix, createBucket));
    }
}
