package com.bank.kyc;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.List;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.ListObjectsV2Request;
import software.amazon.awssdk.services.s3.model.NoSuchBucketException;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;
import software.amazon.awssdk.services.s3.model.S3Object;

/** Documents in an S3 bucket: {@code <prefix><customer>/<name>}. */
public class S3Backend implements DocumentBackend {

    private final S3Client s3;
    private final String bucket;
    private final String prefix;
    private final boolean createBucket;

    public S3Backend(S3Client s3, String bucket, String prefix, boolean createBucket) {
        this.s3 = s3;
        this.bucket = bucket;
        this.prefix = prefix;
        this.createBucket = createBucket;
    }

    @Override
    public long put(String customer, String name, InputStream body) throws IOException {
        // Spool to /tmp so the object length is known before the upload starts.
        Path tmp = Files.createTempFile("kyc-", ".part");
        try {
            long size = Files.copy(body, tmp, StandardCopyOption.REPLACE_EXISTING);
            s3.putObject(PutObjectRequest.builder().bucket(bucket).key(prefix + customer + "/" + name).build(),
                    RequestBody.fromFile(tmp));
            return size;
        } finally {
            Files.deleteIfExists(tmp);
        }
    }

    @Override
    public List<String> list(String customer) {
        String dir = prefix + customer + "/";
        List<String> names = new ArrayList<>();
        ListObjectsV2Request req = ListObjectsV2Request.builder().bucket(bucket).prefix(dir).delimiter("/").build();
        for (S3Object o : s3.listObjectsV2Paginator(req).contents()) {
            names.add(o.key().substring(dir.length()));
        }
        return names;
    }

    @Override
    public void check() {
        try {
            s3.headBucket(b -> b.bucket(bucket));
        } catch (NoSuchBucketException e) {
            if (!createBucket) throw e;
            s3.createBucket(b -> b.bucket(bucket));
        }
    }
}
