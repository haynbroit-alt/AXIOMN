package com.axiomn.assistant

import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.nio.charset.StandardCharsets

/** Mirrors the AXIOMN action payload (see axiomn/action/schema.py). */
data class AxiomnAction(
    val type: String,
    val payload: JSONObject,
)

/** Mirrors the AXIOMN /intent response schema (see axiomn/api/main.py). */
data class AxiomnResult(
    val intent: String,
    val topic: String,
    val language: String,
    val difficulty: Int,
    val confidence: Double,
    val ambiguity: Double,
    val route: String,
    val tool: String,
    val result: String,
    val executionTimeMs: Double,
    val action: AxiomnAction,
)

/**
 * Minimal HTTP client for the AXIOMN backend. Deliberately dependency-free
 * (HttpURLConnection + org.json, both part of the Android SDK) so this file
 * compiles without adding OkHttp/Retrofit/coroutines to the project.
 */
class AxiomnApiClient(private val baseUrl: String) {

    interface Callback {
        fun onSuccess(result: AxiomnResult)
        fun onError(error: Exception)
    }

    /** Blocking call — must be invoked off the main thread. */
    fun classifyIntentBlocking(text: String): AxiomnResult {
        val url = URL("${baseUrl.trimEnd('/')}/intent")
        val connection = url.openConnection() as HttpURLConnection
        try {
            connection.requestMethod = "POST"
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
            connection.connectTimeout = 8000
            connection.readTimeout = 8000

            val payload = JSONObject().put("text", text).toString()
            OutputStreamWriter(connection.outputStream, StandardCharsets.UTF_8).use { it.write(payload) }

            val responseCode = connection.responseCode
            val stream = if (responseCode in 200..299) connection.inputStream else connection.errorStream
            val body = BufferedReader(InputStreamReader(stream, StandardCharsets.UTF_8)).use { it.readText() }

            if (responseCode !in 200..299) {
                throw IllegalStateException("AXIOMN API returned HTTP $responseCode: $body")
            }

            val json = JSONObject(body)
            val actionJson = json.getJSONObject("action")
            return AxiomnResult(
                intent = json.getString("intent"),
                topic = json.getString("topic"),
                language = json.getString("language"),
                difficulty = json.getInt("difficulty"),
                confidence = json.getDouble("confidence"),
                ambiguity = json.getDouble("ambiguity"),
                route = json.getString("route"),
                tool = json.getString("tool"),
                result = json.getString("result"),
                executionTimeMs = json.getDouble("execution_time_ms"),
                action = AxiomnAction(type = actionJson.getString("type"), payload = actionJson.getJSONObject("payload")),
            )
        } finally {
            connection.disconnect()
        }
    }

    /** Runs the request on a plain background thread and calls back on that same thread. */
    fun classifyIntent(text: String, callback: Callback) {
        Thread {
            try {
                callback.onSuccess(classifyIntentBlocking(text))
            } catch (error: Exception) {
                callback.onError(error)
            }
        }.start()
    }
}
