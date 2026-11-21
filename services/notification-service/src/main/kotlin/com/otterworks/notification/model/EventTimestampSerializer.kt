package com.otterworks.notification.model

import kotlinx.serialization.KSerializer
import kotlinx.serialization.SerializationException
import kotlinx.serialization.descriptors.PrimitiveKind
import kotlinx.serialization.descriptors.PrimitiveSerialDescriptor
import kotlinx.serialization.descriptors.SerialDescriptor
import kotlinx.serialization.encoding.Decoder
import kotlinx.serialization.encoding.Encoder
import kotlinx.serialization.json.JsonDecoder
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonPrimitive
import java.time.Instant

/**
 * Decodes the `timestamp` field of an event regardless of which producer
 * generation emitted it. Current producers send an RFC 3339 string; legacy
 * producers send a Unix epoch integer (seconds or milliseconds), sometimes as
 * a numeric string. Every shape is normalised to an ISO-8601 UTC instant so
 * downstream code sees a single format.
 */
object EventTimestampSerializer : KSerializer<String> {
    private const val EPOCH_MILLIS_THRESHOLD = 100_000_000_000L

    override val descriptor: SerialDescriptor =
        PrimitiveSerialDescriptor("com.otterworks.notification.EventTimestamp", PrimitiveKind.STRING)

    override fun serialize(encoder: Encoder, value: String) = encoder.encodeString(value)

    override fun deserialize(decoder: Decoder): String {
        val jsonDecoder = decoder as? JsonDecoder ?: return decoder.decodeString()
        return when (val element = jsonDecoder.decodeJsonElement()) {
            is JsonNull -> ""
            is JsonPrimitive -> normalize(element.content)
            else -> throw SerializationException("timestamp must be a string or a number, got $element")
        }
    }

    internal fun normalize(raw: String): String {
        val value = raw.trim()
        if (value.isEmpty()) return value
        val epoch = value.toLongOrNull() ?: value.toDoubleOrNull()?.toLong()
        if (epoch != null) {
            val instant = if (epoch >= EPOCH_MILLIS_THRESHOLD) Instant.ofEpochMilli(epoch) else Instant.ofEpochSecond(epoch)
            return instant.toString()
        }
        return value
    }
}
