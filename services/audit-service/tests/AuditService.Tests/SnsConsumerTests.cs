using Amazon.SQS;
using Amazon.SQS.Model;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Moq;
using OtterWorks.AuditService.Config;
using OtterWorks.AuditService.Services;

namespace AuditService.Tests;

public class SnsConsumerTests
{
    private const string QueueName = "otterworks-audit-events-queue";
    private const string QueueUrl = "https://sqs.test/audit";

    private readonly Mock<IAmazonSQS> _sqs = new();
    private readonly Mock<IAuditRepository> _repository = new();
    private readonly CancellationTokenSource _cancellation = new();

    [Fact]
    public async Task SnsEnvelopeWithNullPayload_IsNotDeleted_SoQueueCanRedriveIt()
    {
        _sqs.Setup(c => c.GetQueueUrlAsync(QueueName, It.IsAny<CancellationToken>()))
            .ReturnsAsync(new GetQueueUrlResponse { QueueUrl = QueueUrl });
        SetupSingleReceive(new Message
        {
            MessageId = "m-1",
            ReceiptHandle = "r-1",
            Body = "{\"Type\":\"Notification\",\"MessageId\":\"sns-1\",\"Message\":\"null\"}",
        });

        await CreateConsumer().RunAsync(_cancellation.Token);

        VerifyNoDelete();
        _repository.Verify(r => r.SaveEventAsync(It.IsAny<AuditEvent>()), Times.Never);
    }

    [Fact]
    public async Task ValidPayload_IsSavedThenDeleted()
    {
        _sqs.Setup(c => c.GetQueueUrlAsync(QueueName, It.IsAny<CancellationToken>()))
            .ReturnsAsync(new GetQueueUrlResponse { QueueUrl = QueueUrl });
        SetupSingleReceive(new Message
        {
            MessageId = "m-2",
            ReceiptHandle = "r-2",
            Body = "{\"userId\":\"u1\",\"action\":\"create\",\"resourceType\":\"doc\",\"resourceId\":\"d1\"}",
        });

        await CreateConsumer().RunAsync(_cancellation.Token);

        _repository.Verify(r => r.SaveEventAsync(It.Is<AuditEvent>(e => e.Id == "m-2" && e.Action == "create")), Times.Once);
        _sqs.Verify(c => c.DeleteMessageAsync(QueueUrl, "r-2", It.IsAny<CancellationToken>()), Times.Once);
    }

    [Fact]
    public async Task QueueInitializationFailure_IsRetried_InsteadOfStoppingConsumer()
    {
        _sqs.SetupSequence(c => c.GetQueueUrlAsync(QueueName, It.IsAny<CancellationToken>()))
            .ThrowsAsync(new AmazonSQSException("transient"))
            .ThrowsAsync(new AmazonSQSException("transient"))
            .ReturnsAsync(new GetQueueUrlResponse { QueueUrl = QueueUrl });
        SetupSingleReceive();
        var consumer = CreateConsumer();

        await consumer.RunAsync(_cancellation.Token);

        Assert.Equal(2, consumer.Delays.Count);
        _sqs.Verify(c => c.GetQueueUrlAsync(QueueName, It.IsAny<CancellationToken>()), Times.Exactly(3));
        _sqs.Verify(c => c.ReceiveMessageAsync(
            It.Is<ReceiveMessageRequest>(r => r.QueueUrl == QueueUrl), It.IsAny<CancellationToken>()), Times.Once);
    }

    [Fact]
    public async Task QueueInitialization_StopsRetryingOnShutdown()
    {
        _sqs.Setup(c => c.GetQueueUrlAsync(QueueName, It.IsAny<CancellationToken>()))
            .ThrowsAsync(new AmazonSQSException("down"));
        var consumer = CreateConsumer(onDelay: () => _cancellation.Cancel());

        await consumer.RunAsync(_cancellation.Token);

        Assert.Single(consumer.Delays);
        _sqs.Verify(c => c.ReceiveMessageAsync(It.IsAny<ReceiveMessageRequest>(), It.IsAny<CancellationToken>()), Times.Never);
    }

    [Theory]
    [InlineData(1, 1)]
    [InlineData(3, 4)]
    [InlineData(7, 60)]
    [InlineData(1000, 60)]
    public void InitRetryDelay_IsExponentialWithJitterAndCapped(int attempt, double capSeconds)
    {
        for (var i = 0; i < 50; i++)
        {
            var delay = TestableSnsConsumer.Delay(attempt).TotalSeconds;
            Assert.InRange(delay, capSeconds / 2, capSeconds);
        }
    }

    private void SetupSingleReceive(params Message[] messages)
    {
        _sqs.Setup(c => c.ReceiveMessageAsync(It.IsAny<ReceiveMessageRequest>(), It.IsAny<CancellationToken>()))
            .Callback(() => _cancellation.Cancel())
            .ReturnsAsync(new ReceiveMessageResponse { Messages = messages.ToList() });
    }

    private void VerifyNoDelete()
    {
        _sqs.Verify(c => c.DeleteMessageAsync(It.IsAny<string>(), It.IsAny<string>(), It.IsAny<CancellationToken>()), Times.Never);
        _sqs.Verify(c => c.DeleteMessageAsync(It.IsAny<DeleteMessageRequest>(), It.IsAny<CancellationToken>()), Times.Never);
    }

    private TestableSnsConsumer CreateConsumer(Action? onDelay = null) =>
        new(_sqs.Object, _repository.Object, Mock.Of<ILogger<SnsConsumer>>(), onDelay);

    private sealed class TestableSnsConsumer : SnsConsumer
    {
        private readonly Action? _onDelay;

        public TestableSnsConsumer(IAmazonSQS sqs, IAuditRepository repository, ILogger<SnsConsumer> logger, Action? onDelay)
            : base(sqs, repository, Options.Create(new AwsSettings()), logger)
        {
            _onDelay = onDelay;
        }

        public List<TimeSpan> Delays { get; } = new();

        public static TimeSpan Delay(int attempt) => InitRetryDelay(attempt);

        public Task RunAsync(CancellationToken ct) => ExecuteAsync(ct);

        protected override Task DelayAsync(TimeSpan delay, CancellationToken ct)
        {
            Delays.Add(delay);
            _onDelay?.Invoke();
            return ct.IsCancellationRequested ? Task.FromCanceled(ct) : Task.CompletedTask;
        }
    }
}
