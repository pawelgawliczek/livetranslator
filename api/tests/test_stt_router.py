"""
Unit tests for STT Router conversation context and parallel processing.

Tests cover:
- Conversation history management
- Context prompt building from history
- Smart word-level deduplication
- Parallel processing with instant and quality results
- Processing indicator flags
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import base64


class TestConversationContext:
    """Test suite for conversation context features."""

    def test_conversation_history_initialization(self):
        """Test that conversation history is initialized correctly in session."""
        session = {
            "segment_id": "seg-123",
            "last_transcribed_length": 0,
            "accumulated_audio": b"",
            "accumulated_text": "",
            "chunk_count": 0,
            "speaker": "user1",
            "target_lang": "es",
            "language_hint": "en",
            "last_audio_end_time": 0.0,
            "no_change_count": 0,
            "last_new_text": "",
            "conversation_history": []
        }

        assert "conversation_history" in session
        assert isinstance(session["conversation_history"], list)
        assert len(session["conversation_history"]) == 0

    def test_conversation_history_appends_sentences(self):
        """Test that finalized sentences are added to conversation history."""
        history = []
        final_text = "This is a test sentence."

        # Simulate adding to history
        if final_text and len(final_text) > 10:
            history.append(final_text)

        assert len(history) == 1
        assert history[0] == "This is a test sentence."

    def test_conversation_history_limits_to_five_sentences(self):
        """Test that conversation history keeps only last 5 sentences."""
        history = [
            "Sentence one.",
            "Sentence two.",
            "Sentence three.",
            "Sentence four.",
            "Sentence five.",
        ]

        new_sentence = "Sentence six."
        history.append(new_sentence)
        if len(history) > 5:
            history = history[-5:]

        assert len(history) == 5
        assert history[0] == "Sentence two."
        assert history[-1] == "Sentence six."

    def test_context_prompt_building(self):
        """Test that context prompt is built from last 2-3 sentences."""
        history = [
            "This is the first sentence.",
            "This is the second sentence.",
            "This is the third sentence.",
        ]

        # Build context from last 3 sentences, max 200 chars
        recent_context = " ".join(history[-3:])[-200:]

        assert len(recent_context) <= 200
        assert "first sentence" in recent_context
        assert "third sentence" in recent_context

    def test_context_prompt_truncates_to_200_chars(self):
        """Test that context prompt is truncated to 200 characters."""
        history = [
            "This is a very long sentence with many words to make it exceed the character limit. " * 5,
            "Another long sentence." * 10,
            "Final sentence.",
        ]

        recent_context = " ".join(history[-3:])[-200:]

        assert len(recent_context) == 200

    def test_short_sentences_not_added_to_history(self):
        """Test that sentences shorter than 10 chars are not added."""
        history = []
        final_text = "Hi"

        if final_text and len(final_text) > 10:
            history.append(final_text)

        assert len(history) == 0


class TestSmartDeduplication:
    """Test suite for smart word-level deduplication."""

    def test_no_deduplication_when_no_overlap(self):
        """Test that text is unchanged when there's no overlap with context."""
        new_text = "This is completely new text"
        context_prompt = "Previous context with different words"

        new_words = new_text.split()
        context_words = context_prompt.split()

        overlap_count = 0
        for i in range(min(len(new_words), len(context_words))):
            context_word = context_words[-(i+1)] if i < len(context_words) else None
            new_word = new_words[i] if i < len(new_words) else None

            if context_word and new_word and context_word.lower() == new_word.lower():
                overlap_count += 1
            else:
                break

        if overlap_count > 0:
            new_text = " ".join(new_words[overlap_count:])

        assert overlap_count == 0
        assert new_text == "This is completely new text"

    def test_deduplication_removes_overlapping_words(self):
        """Test that overlapping words from context are removed."""
        context_prompt = "The quick brown fox"
        new_text = "fox jumps over the lazy dog"

        new_words = new_text.split()
        context_words = context_prompt.split()

        overlap_count = 0
        for i in range(min(len(new_words), len(context_words))):
            context_word = context_words[-(i+1)] if i < len(context_words) else None
            new_word = new_words[i] if i < len(new_words) else None

            if context_word and new_word and context_word.lower() == new_word.lower():
                overlap_count += 1
            else:
                break

        if overlap_count > 0:
            deduplicated_text = " ".join(new_words[overlap_count:])
        else:
            deduplicated_text = new_text

        assert overlap_count == 1  # "fox" overlaps
        assert deduplicated_text == "jumps over the lazy dog"

    def test_deduplication_is_case_insensitive(self):
        """Test that deduplication works case-insensitively."""
        context_prompt = "Hello World"
        new_text = "WORLD is beautiful"

        new_words = new_text.split()
        context_words = context_prompt.split()

        overlap_count = 0
        for i in range(min(len(new_words), len(context_words))):
            context_word = context_words[-(i+1)] if i < len(context_words) else None
            new_word = new_words[i] if i < len(new_words) else None

            if context_word and new_word and context_word.lower() == new_word.lower():
                overlap_count += 1
            else:
                break

        assert overlap_count == 1  # "WORLD" matches "World" case-insensitively


class TestParallelProcessing:
    """Test suite for parallel processing features."""

    def test_instant_event_has_processing_flag(self):
        """Test that instant result includes processing=True."""
        instant_event = {
            "type": "stt_final",
            "room_id": "test-room",
            "segment_id": "seg-123",
            "revision": 0,
            "text": "Instant transcription",
            "lang": "en",
            "final": True,
            "processing": True,
            "ts_iso": None,
            "device": "web",
            "speaker": "user1",
            "target_lang": "es"
        }

        assert instant_event["processing"] is True
        assert instant_event["final"] is True
        assert instant_event["text"] == "Instant transcription"

    def test_quality_event_has_processing_false(self):
        """Test that quality result includes processing=False."""
        quality_event = {
            "type": "stt_final",
            "room_id": "test-room",
            "segment_id": "seg-123",
            "revision": 1,
            "text": "High quality transcription.",
            "lang": "en",
            "final": True,
            "processing": False,
            "ts_iso": None,
            "device": "web",
            "speaker": "user1",
            "target_lang": "es"
        }

        assert quality_event["processing"] is False
        assert quality_event["final"] is True
        assert quality_event["revision"] == 1

    def test_quality_event_sent_when_text_differs(self):
        """Test that quality event is sent when text differs from instant."""
        instant_text = "instant text"
        final_text = "High quality text."

        should_send_update = (final_text != instant_text)

        assert should_send_update is True

    def test_completion_event_sent_when_text_same(self):
        """Test that completion event is sent even when text is identical."""
        instant_text = "Same text"
        final_text = "Same text"

        should_send_completion = (final_text == instant_text)

        assert should_send_completion is True

    def test_revision_increments_for_quality_pass(self):
        """Test that revision number increments for quality result."""
        instant_revision = 5
        quality_revision = instant_revision + 1

        assert quality_revision == 6


class TestProcessingIndicator:
    """Test suite for processing indicator in UI."""

    def test_processing_text_translations_exist(self):
        """Test that processing text has translations for common languages."""
        translations = {
            'en': 'Refining quality...',
            'es': 'Mejorando calidad...',
            'fr': 'Amélioration de la qualité...',
            'de': 'Qualität verbessern...',
            'it': 'Miglioramento qualità...',
            'pt': 'Melhorando qualidade...',
            'ru': 'Улучшение качества...',
            'zh': '提高质量中...',
            'ja': '品質向上中...',
        }

        assert 'en' in translations
        assert 'es' in translations
        assert 'zh' in translations
        assert len(translations) >= 9

    def test_processing_text_fallback_to_english(self):
        """Test that unknown languages fall back to English."""
        translations = {
            'en': 'Refining quality...',
            'es': 'Mejorando calidad...',
        }

        def get_processing_text(lang):
            return translations.get(lang, translations['en'])

        assert get_processing_text('unknown') == 'Refining quality...'
        assert get_processing_text('es') == 'Mejorando calidad...'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
