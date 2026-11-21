package com.otterworks.notification.model

import kotlinx.serialization.KSerializer
import kotlinx.serialization.SerializationException
import kotlinx.serialization.descriptors.PrimitiveKind
import kotlinx.serialization.descriptors.PrimitiveSerialDescriptor
import kotlinx.serialization.descriptors.SerialDescriptor
import kotlinx.serialization.encoding.Decoder
import kotlinx.serialization.encoding.Encoder
import kotlinx.serialization.json.JsonDecoder
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.longOrNull
import java.time.Instant

/**
 * Decodes the `timestamp` field of queue events into an ISO-8601 string.
 *
 * Current producers send RFC 3339 strings; legacy producers (and the admin
 * chaos probe) send Unix epoch numbers, in seconds or milliseconds. Both are
 * accepted here regardless of how strict the surrounding Json instance is, so
 * a schema difference between producers can never turn into a poison message.
 */
object EventTimestampSerializer : KSerializer<String> {
    private const val EPOCH_MILLIS_THRESHOLD = 100_000_000_000L

    override val descriptor: SerialDescriptor =
        PrimitiveSerialDescriptor("EventTimestamp", PrimitiveKind.STRING)

    override fun serialize(encoder: Encoder, value: String) = encoder.encodeString(value)

    override fun deserialize(decoder: Decoder): String {
        val jsonDecoder = decoder as? JsonDecoder ?: return decoder.decodeString()
        val element = jsonDecoder.decodeJsonElement()
        val primitive = element as? JsonPrimitive
            ?: throw SerializationException("timestamp must be a string or a number, got $element")
        if (primitive.isString) {
            return primitive.content
        }
        val epoch = primitive.longOrNull
            ?: primitive.doubleOrNull?.toLong()
            ?: throw SerializationException("timestamp must be a string or a number, got ${primitive.content}")
        return fromEpoch(epoch).toString()
    }

    internal fun fromEpoch(value: Long): Instant =
        if (value >= EPOCH_MILLIS_THRESHOLD) Instant.ofEpochMilli(value) else Instant.ofEpochSecond(value)
}
