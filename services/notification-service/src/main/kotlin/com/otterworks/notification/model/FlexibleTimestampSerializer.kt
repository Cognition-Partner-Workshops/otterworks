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
 * Accepts the timestamp formats emitted by every producer version on the
 * notifications topic and normalises them to an ISO-8601 UTC string:
 *
 *  - RFC 3339 / ISO-8601 strings (current producers), passed through as-is
 *  - Unix epoch integers in seconds or milliseconds (legacy producers)
 *  - Unix epoch floats in seconds with a fractional part
 *
 * Epoch values at or above [EPOCH_MILLIS_THRESHOLD] are read as milliseconds;
 * anything smaller is seconds. The boundary is year 5138 in seconds and 1973
 * in milliseconds, so no realistic event timestamp is ambiguous.
 */
object FlexibleTimestampSerializer : KSerializer<String> {
    private const val EPOCH_MILLIS_THRESHOLD = 100_000_000_000L

    override val descriptor: SerialDescriptor =
        PrimitiveSerialDescriptor("com.otterworks.notification.FlexibleTimestamp", PrimitiveKind.STRING)

    override fun deserialize(decoder: Decoder): String {
        val jsonDecoder = decoder as? JsonDecoder ?: return decoder.decodeString()
        val element = jsonDecoder.decodeJsonElement()
        val primitive = element as? JsonPrimitive
            ?: throw SerializationException("timestamp must be a string or a number, got $element")

        if (primitive.isString) return primitive.content

        primitive.longOrNull?.let { return fromEpoch(it) }
        primitive.doubleOrNull?.let { seconds ->
            return Instant.ofEpochMilli((seconds * 1000).toLong()).toString()
        }
        throw SerializationException("timestamp must be a string or a number, got ${primitive.content}")
    }

    override fun serialize(encoder: Encoder, value: String) = encoder.encodeString(value)

    internal fun fromEpoch(value: Long): String {
        val instant = if (value >= EPOCH_MILLIS_THRESHOLD) Instant.ofEpochMilli(value) else Instant.ofEpochSecond(value)
        return instant.toString()
    }
}
