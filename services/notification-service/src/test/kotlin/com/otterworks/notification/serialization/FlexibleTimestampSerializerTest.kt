package com.otterworks.notification.serialization

import kotlinx.serialization.SerializationException
import kotlinx.serialization.json.JsonPrimitive
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class FlexibleTimestampSerializerTest {

    @Test
    fun `passes RFC 3339 strings through unchanged`() {
        assertEquals(
            "2024-06-15T10:30:00+01:00",
            FlexibleTimestampSerializer.normalize(JsonPrimitive("2024-06-15T10:30:00+01:00")),
        )
    }

    @Test
    fun `converts epoch seconds to ISO instant`() {
        assertEquals("2024-01-01T00:00:00Z", FlexibleTimestampSerializer.normalize(JsonPrimitive(1704067200L)))
    }

    @Test
    fun `converts epoch milliseconds to ISO instant`() {
        assertEquals("2024-01-01T00:00:00.123Z", FlexibleTimestampSerializer.normalize(JsonPrimitive(1704067200123L)))
    }

    @Test
    fun `converts fractional epoch seconds to ISO instant`() {
        assertEquals("2024-01-01T00:00:00Z", FlexibleTimestampSerializer.normalize(JsonPrimitive(1704067200.75)))
    }

    @Test
    fun `converts numeric strings as epoch seconds`() {
        assertEquals("2024-01-01T00:00:00Z", FlexibleTimestampSerializer.normalize(JsonPrimitive(" 1704067200 ")))
    }

    @Test
    fun `rejects non-temporal primitives`() {
        assertFailsWith<SerializationException> {
            FlexibleTimestampSerializer.normalize(JsonPrimitive(true))
        }
    }
}
