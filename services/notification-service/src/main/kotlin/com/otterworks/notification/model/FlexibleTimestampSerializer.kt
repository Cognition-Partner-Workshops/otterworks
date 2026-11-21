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
import java.time.format.DateTimeFormatter
import kotlin.math.abs

/**
 * Producers disagree on the wire format of `timestamp`: current services send
 * an RFC 3339 string, legacy producers send a Unix epoch number (seconds or
 * milliseconds). Every form decodes to an ISO-8601 UTC string so the rest of
 * the service only ever sees one representation, whatever the parser settings.
 */
object FlexibleTimestampSerializer : KSerializer<String> {
    private const val EPOCH_MILLIS_THRESHOLD = 100_000_000_000L

    override val descriptor: SerialDescriptor =
        PrimitiveSerialDescriptor("com.otterworks.notification.FlexibleTimestamp", PrimitiveKind.STRING)

    override fun serialize(encoder: Encoder, value: String) = encoder.encodeString(value)

    override fun deserialize(decoder: Decoder): String {
        val jsonDecoder = decoder as? JsonDecoder ?: return decoder.decodeString()
        val element = jsonDecoder.decodeJsonElement()
        val primitive = element as? JsonPrimitive
            ?: throw SerializationException("timestamp must be a string or a number, got $element")
        if (primitive.isString) {
            return primitive.content.toLongOrNull()?.let(::epochToIso) ?: primitive.content
        }
        val epoch = primitive.longOrNull ?: primitive.doubleOrNull?.toLong()
            ?: throw SerializationException("timestamp must be a string or a number, got ${primitive.content}")
        return epochToIso(epoch)
    }

    internal fun epochToIso(epoch: Long): String {
        val instant = if (abs(epoch) >= EPOCH_MILLIS_THRESHOLD) Instant.ofEpochMilli(epoch) else Instant.ofEpochSecond(epoch)
        return DateTimeFormatter.ISO_INSTANT.format(instant)
    }
}
