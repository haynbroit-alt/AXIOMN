package com.axiomn.assistant

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.view.MotionEvent
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import java.util.Locale

/**
 * "Zero choice" push-to-talk MVP: hold the button, speak, release — AXIOMN
 * classifies the request, routes it, and speaks the result back. There is
 * no wake word and no background/foreground service here on purpose: those
 * need real-device testing (battery exemptions, always-on mic UX) that this
 * repo's CI/sandbox environment cannot verify, so this MVP sticks to a flow
 * that a developer can build and try in Android Studio.
 */
class MainActivity : AppCompatActivity(), TextToSpeech.OnInitListener {

    private lateinit var serverUrlInput: EditText
    private lateinit var micButton: Button
    private lateinit var transcriptView: TextView
    private lateinit var answerView: TextView
    private lateinit var thoughtView: TextView

    private var speechRecognizer: SpeechRecognizer? = null
    private var textToSpeech: TextToSpeech? = null
    private var ttsReady = false

    private val requestMicPermission = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) {
            startListening()
        } else {
            transcriptView.text = "Microphone permission is required for AXIOMN to hear you."
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        serverUrlInput = findViewById(R.id.serverUrlInput)
        micButton = findViewById(R.id.micButton)
        transcriptView = findViewById(R.id.transcriptView)
        answerView = findViewById(R.id.answerView)
        thoughtView = findViewById(R.id.thoughtView)

        textToSpeech = TextToSpeech(this, this)

        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            micButton.isEnabled = false
            transcriptView.text = "No speech recognizer available on this device."
        }

        micButton.setOnTouchListener { _, event ->
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    ensureMicPermissionThenListen()
                    true
                }
                MotionEvent.ACTION_UP -> {
                    speechRecognizer?.stopListening()
                    true
                }
                else -> false
            }
        }
    }

    override fun onInit(status: Int) {
        ttsReady = status == TextToSpeech.SUCCESS
    }

    private fun ensureMicPermissionThenListen() {
        val granted = checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
        if (granted) {
            startListening()
        } else {
            requestMicPermission.launch(Manifest.permission.RECORD_AUDIO)
        }
    }

    private fun startListening() {
        micButton.text = getString(R.string.mic_button_listening)
        answerView.text = ""
        thoughtView.text = ""

        val recognizer = SpeechRecognizer.createSpeechRecognizer(this)
        speechRecognizer = recognizer

        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            // No fixed locale: AXIOMN's intent engine is designed to classify
            // across languages, so let the recognizer use the device default.
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
        }

        recognizer.setRecognitionListener(object : RecognitionListener {
            override fun onReadyForSpeech(params: Bundle?) {}
            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(rmsdB: Float) {}
            override fun onBufferReceived(buffer: ByteArray?) {}
            override fun onEndOfSpeech() {}

            override fun onError(error: Int) {
                micButton.text = getString(R.string.mic_button_idle)
                transcriptView.text = "Didn't catch that (error code $error). Try again."
                releaseRecognizer()
            }

            override fun onResults(results: Bundle?) {
                val text = results
                    ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    ?.firstOrNull()
                releaseRecognizer()

                if (text.isNullOrBlank()) {
                    micButton.text = getString(R.string.mic_button_idle)
                    return
                }
                transcriptView.text = "\"$text\""
                askAxiomn(text)
            }

            override fun onPartialResults(partialResults: Bundle?) {}
            override fun onEvent(eventType: Int, params: Bundle?) {}
        })

        recognizer.startListening(intent)
    }

    private fun releaseRecognizer() {
        speechRecognizer?.destroy()
        speechRecognizer = null
    }

    private fun askAxiomn(text: String) {
        micButton.text = getString(R.string.mic_button_thinking)
        val baseUrl = serverUrlInput.text.toString().trim().ifEmpty { "http://10.0.2.2:8000" }

        AxiomnApiClient(baseUrl).classifyIntent(text, object : AxiomnApiClient.Callback {
            override fun onSuccess(result: AxiomnResult) {
                runOnUiThread {
                    micButton.text = getString(R.string.mic_button_idle)
                    answerView.text = result.result
                    thoughtView.text = buildString {
                        append("intent: ${result.intent}  (confidence ${result.confidence})\n")
                        append("language: ${result.language}  difficulty: ${result.difficulty}/10\n")
                        append("route: ${result.route}  tool: ${result.tool}\n")
                        append("execution_time_ms: ${result.executionTimeMs}")
                    }
                    speak(result.result)
                }
            }

            override fun onError(error: Exception) {
                runOnUiThread {
                    micButton.text = getString(R.string.mic_button_idle)
                    answerView.text = "Couldn't reach AXIOMN: ${error.message}"
                }
            }
        })
    }

    private fun speak(text: String) {
        if (ttsReady) {
            textToSpeech?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "axiomn-answer")
        }
    }

    override fun onDestroy() {
        releaseRecognizer()
        textToSpeech?.stop()
        textToSpeech?.shutdown()
        super.onDestroy()
    }
}
