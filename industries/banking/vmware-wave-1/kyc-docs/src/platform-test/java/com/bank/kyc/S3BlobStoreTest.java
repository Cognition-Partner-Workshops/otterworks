package com.bank.kyc;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

import java.io.ByteArrayInputStream;
import java.io.FilterInputStream;
import java.net.InetSocketAddress;
import java.util.List;
import java.util.concurrent.atomic.AtomicReference;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.*;

class S3BlobStoreTest {
    private final S3Client client = mock(S3Client.class);
    private final S3BlobStore store = new S3BlobStore(client, "documents");

    @Test
    void customEndpointReceivesOnlyFileBytesWithoutAwsChunkFrames() throws Exception {
        AtomicReference<byte[]> received = new AtomicReference<>();
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/documents/HG611000001/a.pdf", exchange -> {
            received.set(exchange.getRequestBody().readAllBytes());
            exchange.sendResponseHeaders(200, -1);
            exchange.close();
        });
        String oldKey = System.getProperty("aws.accessKeyId");
        String oldSecret = System.getProperty("aws.secretAccessKey");
        try {
            System.setProperty("aws.accessKeyId", "synthetic-unit-test");
            System.setProperty("aws.secretAccessKey", "synthetic-unit-test-only");
            server.start();
            S3BlobStore httpStore = new S3BlobStore("documents",
                    "http://127.0.0.1:" + server.getAddress().getPort(), "us-east-1", true);
            byte[] fixture = new byte[]{0, 1, 2, 3, -1};
            FilterInputStream input = new FilterInputStream(new ByteArrayInputStream(fixture)) {
                @Override public boolean markSupported() { return false; }
            };
            assertEquals(fixture.length, httpStore.put("HG611000001/a.pdf", input, fixture.length));
            assertArrayEquals(fixture, received.get());
        } finally {
            server.stop(0);
            if (oldKey == null) System.clearProperty("aws.accessKeyId");
            else System.setProperty("aws.accessKeyId", oldKey);
            if (oldSecret == null) System.clearProperty("aws.secretAccessKey");
            else System.setProperty("aws.secretAccessKey", oldSecret);
        }
    }

    @Test
    void putsExactKeyAndContentLengthIncludingEmptyFile() throws Exception {
        for (byte[] bytes : new byte[][]{new byte[]{1, 2, 3}, new byte[0]}) {
            assertEquals(bytes.length, store.put("HG611000001/passport-1.pdf",
                    new ByteArrayInputStream(bytes), bytes.length));
        }
        ArgumentCaptor<PutObjectRequest> requests = ArgumentCaptor.forClass(PutObjectRequest.class);
        ArgumentCaptor<RequestBody> bodies = ArgumentCaptor.forClass(RequestBody.class);
        verify(client, times(2)).putObject(requests.capture(), bodies.capture());
        assertEquals("documents", requests.getAllValues().get(0).bucket());
        assertEquals("HG611000001/passport-1.pdf", requests.getValue().key());
        assertEquals(3L, requests.getAllValues().get(0).contentLength());
        assertEquals(3L, bodies.getAllValues().get(0).optionalContentLength().orElseThrow());
        assertEquals(0L, requests.getValue().contentLength());
    }

    @Test
    void listsAllPagesSortedAndHandlesEmptyBucket() {
        when(client.listObjectsV2(any(ListObjectsV2Request.class))).thenReturn(
                ListObjectsV2Response.builder().contents(S3Object.builder().key("HG611000001/z.pdf").build())
                        .isTruncated(true).nextContinuationToken("page2").build(),
                ListObjectsV2Response.builder().contents(S3Object.builder().key("HG611000001/a.pdf").build())
                        .isTruncated(false).build(),
                ListObjectsV2Response.builder().build());
        assertEquals(List.of("a.pdf", "z.pdf"), store.list("HG611000001"));
        assertEquals(List.of(), store.list("HG611000001"));
        ArgumentCaptor<ListObjectsV2Request> requests = ArgumentCaptor.forClass(ListObjectsV2Request.class);
        verify(client, times(3)).listObjectsV2(requests.capture());
        assertEquals("documents", requests.getValue().bucket());
        assertEquals("HG611000001/", requests.getValue().prefix());
        assertEquals("page2", requests.getAllValues().get(1).continuationToken());
    }

    @Test
    void healthChecksBucketAndFailuresAreNotHealthy() {
        when(client.headBucket(any(HeadBucketRequest.class))).thenReturn(HeadBucketResponse.builder().build())
                .thenThrow(S3Exception.builder().statusCode(503).build());
        assertTrue(store.healthy());
        assertFalse(store.healthy());
        verify(client, times(2)).headBucket(HeadBucketRequest.builder().bucket("documents").build());
    }

    @Test
    void storageErrorsPropagate() {
        when(client.putObject(any(PutObjectRequest.class), any(RequestBody.class)))
                .thenThrow(S3Exception.builder().statusCode(503).build());
        when(client.listObjectsV2(any(ListObjectsV2Request.class)))
                .thenThrow(S3Exception.builder().statusCode(503).build());
        assertThrows(S3Exception.class, () -> store.put("HG611000001/a.pdf", new ByteArrayInputStream(new byte[0]), 0));
        assertThrows(S3Exception.class, () -> store.list("HG611000001"));
    }

    @Test
    void rejectsIncorrectSizeBeforeUploading() {
        assertThrows(java.io.IOException.class,
                () -> store.put("HG611000001/a.pdf", new ByteArrayInputStream(new byte[3]), 4));
        verifyNoInteractions(client);
    }
}
