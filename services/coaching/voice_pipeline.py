import time
import base64
import streamlit as st
import streamlit.components.v1 as components


class VoicePipeline:
    def __init__(self, llm, tts):
        self.llm = llm
        self.tts = tts
        self.last_spoken_at = 0

    def _find_form_issue(self, exercise, metrics):
        if "issue" in metrics:
            return metrics["issue"]

        if exercise == "Squats":
            depth = metrics.get("depth_status", "")
            back_angle = metrics.get("back_angle", 180)

            if depth == "TOO HIGH":
                return "The user's squat is not deep enough — knees are not bending sufficiently."

            if isinstance(back_angle, (int, float)) and back_angle < 130:
                return "The user is leaning too far forward during the squat."

        elif exercise == "Push-ups":
            alignment = metrics.get("body_alignment", "")
            hip_status = metrics.get("hip_status", "")

            if alignment == "Poor Form":
                return "The user's body is not straight during the push-up."

            if hip_status == "SAGGING":
                return "The user's hips are sagging down during the push-up."

            if hip_status == "PIKED UP":
                return "The user's hips are too high — lower them to form a straight line."

        elif exercise == "Biceps Curls (Dumbbell)":
            swing = metrics.get("swing_status", "")
            shoulder = metrics.get("shoulder_status", "")

            if swing == "SWINGING":
                return "The user is swinging their torso during the curl — keep the body still."

            if shoulder == "ELBOW DRIFTING":
                return "The user's elbow is drifting away from their side during the curl."

        elif exercise == "Shoulder Press":
            back_arch = metrics.get("back_arch_status", "")

            if back_arch == "Excessive Arch":
                return "The user is arching their lower back excessively during the press."

            if back_arch == "Slight Arch":
                return "Slight back arch detected — encourage the user to brace their core."

        elif exercise == "Lunges":
            balance = metrics.get("balance_status", "")

            if balance == "OFF BALANCE":
                return "The user is losing balance during the lunge — feet should be hip-width apart."

        return None

    def process_event(self, event, exercise, metrics):
        issue = self._find_form_issue(exercise, metrics)

        now = time.time()

        is_major_event = event in ["workout_started", "set_completed", "workout_completed"]

        if not is_major_event:
            if not issue:
                return None

            if now - self.last_spoken_at < 5:
                return None

        try:
            text = self.llm.give_feedback(event, issue)
            voice = self.tts.speak(text)
        except Exception as e:
            st.warning(f"🔇 Voice pipeline error: {e}")
            return None

        if not voice:
            st.warning("🔇 TTS returned no audio.")
            return None

        self.last_spoken_at = now

        return voice, text


def autoplay_audio(audio_bytes):
    """Play audio using the Web Audio API (AudioContext.decodeAudioData).

    This is the most reliable autoplay method in Streamlit because:
    - It runs directly in the parent page JS context (no iframe sandbox).
    - AudioContext.resume() re-activates a suspended context caused by
      the browser autoplay policy — the prior 'Start Workout' click
      satisfies the user-gesture requirement, so resume() succeeds.
    - Avoids all <audio> element / src blob URL restrictions.
    """
    if not audio_bytes:
        return

    b64 = base64.b64encode(audio_bytes).decode("utf-8")

    components.html(
        f"""
        <script>
        (function() {{
            const b64 = "{b64}";

            // Decode base64 -> ArrayBuffer
            const binary = atob(b64);
            const len = binary.length;
            const bytes = new Uint8Array(len);
            for (let i = 0; i < len; i++) {{
                bytes[i] = binary.charCodeAt(i);
            }}
            const arrayBuffer = bytes.buffer;

            // Use Web Audio API to decode and play
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (!AudioContext) {{
                console.warn("AudioContext not supported in this browser.");
                return;
            }}

            const ctx = new AudioContext();

            // Resume in case the context is suspended (browser autoplay policy)
            ctx.resume().then(function() {{
                ctx.decodeAudioData(arrayBuffer, function(audioBuffer) {{
                    const source = ctx.createBufferSource();
                    source.buffer = audioBuffer;
                    source.connect(ctx.destination);
                    source.start(0);
                }}, function(err) {{
                    console.error("Audio decode error:", err);
                }});
            }}).catch(function(err) {{
                console.error("AudioContext resume error:", err);
            }});
        }})();
        </script>
        """,
        height=0,
    )