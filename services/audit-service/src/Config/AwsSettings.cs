namespace OtterWorks.AuditService.Config;

public class AwsSettings
{
    public string Region { get; set; } = "us-east-1";
    public string? EndpointUrl { get; set; }
    public string DynamoDbTable { get; set; } = "otterworks-audit-events";
    public string S3ArchiveBucket { get; set; } = "otterworks-audit-archive";

    // Key prefix for exports/archives, e.g. "tenants/<id>/" for an ephemeral
    // tenant whose IAM role may only write under that prefix. Empty = none.
    public string S3ArchivePrefix { get; set; } = string.Empty;
    public string? SnsTopicArn { get; set; }
    public int ArchiveAfterDays { get; set; } = 90;
}
