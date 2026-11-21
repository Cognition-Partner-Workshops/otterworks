package com.otterworks.notification.serialization

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
import java.time.format.DateTimeFormatter

/**
 * Accepts the timestamp formats seen on the notifications queue and always
 * yields an RFC 3339 / ISO-8601 UTC string:
 *
 *  - `"2024-01-01T00:00:00Z"`       current producers (file, document, collab services)
 *  - `1704067200` / `"1704067200"`  legacy producers: Unix epoch seconds
 *  - `1704067200000`                legacy producers: Unix epoch milliseconds
 *
 * Epoch values at or above [EPOCH_MILLIS_THRESHOLD] are treated as milliseconds
 * (epoch seconds would not reach that value until the year 5138).
 */
object FlexibleTimestampSerializer : KSerializer<String> {
    private const val EPOCH_MILLIS_THRESHOLD = 100_000_000_000L

    override val descriptor: SerialDescriptor =
        PrimitiveSerialDescriptor("com.otterworks.notification.FlexibleTimestamp", PrimitiveKind.STRING)

    override fun serialize(encoder: Encoder, value: String) = encoder.encodeString(value)

    override fun deserialize(decoder: Decoder): String {
        val jsonDecoder = decoder as? JsonDecoder
            ?: return decoder.decodeString()
        val element = jsonDecoder.decodeJsonElement()
        val primitive = element as? JsonPrimitive
            ?: throw SerializationException("timestamp must be a string or number, got $element")
        return normalize(primitive)
    }

    internal fun normalize(primitive: JsonPrimitive): String {
        if (primitive.isString) {
            val text = primitive.content.trim()
            text.toLongOrNull()?.let { return epochToIso(it) }
            return text
        }
        primitive.longOrNull?.let { return epochToIso(it) }
        primitive.doubleOrNull?.let { return epochToIso(it.toLong()) }
        throw SerializationException("timestamp must be a string or number, got $primitive")
    }

    private fun epochToIso(epoch: Long): String {
        val instant = if (epoch >= EPOCH_MILLIS_THRESHOLD) {
            Instant.ofEpochMilli(epoch)
        } else {
            Instant.ofEpochSecond(epoch)
        }
        return DateTimeFormatter.ISO_INSTANT.format(instant)
    }
}
