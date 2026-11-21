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
 * Accepts the two timestamp encodings that reach the notifications queue:
 * RFC 3339 strings from current publishers and Unix epoch numbers (seconds or
 * milliseconds) from legacy publishers. Numbers are normalised to RFC 3339 so
 * downstream code only ever sees a string.
 */
object EventTimestampSerializer : KSerializer<String> {
    private const val EPOCH_MILLIS_THRESHOLD = 100_000_000_000L

    override val descriptor: SerialDescriptor =
        PrimitiveSerialDescriptor("com.otterworks.notification.EventTimestamp", PrimitiveKind.STRING)

    override fun serialize(encoder: Encoder, value: String) = encoder.encodeString(value)

    override fun deserialize(decoder: Decoder): String {
        val jsonDecoder = decoder as? JsonDecoder
            ?: return decoder.decodeString()
        val element = jsonDecoder.decodeJsonElement()
        val primitive = element as? JsonPrimitive
            ?: throw SerializationException("timestamp must be a string or a number, got $element")
        if (primitive.isString) return primitive.content
        return fromEpoch(primitive)
    }

    fun fromEpoch(primitive: JsonPrimitive): String {
        primitive.longOrNull?.let { return fromEpoch(it) }
        primitive.doubleOrNull?.let { return fromEpoch(it.toLong()) }
        throw SerializationException("timestamp must be a string or a number, got $primitive")
    }

    fun fromEpoch(epoch: Long): String {
        val instant = if (epoch >= EPOCH_MILLIS_THRESHOLD) Instant.ofEpochMilli(epoch) else Instant.ofEpochSecond(epoch)
        return instant.toString()
    }
}
