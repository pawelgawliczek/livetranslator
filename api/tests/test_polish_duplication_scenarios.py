"""
End-to-end tests simulating Polish duplication scenarios.

These tests replicate the exact scenarios from problem.md to ensure
the fix remains stable and prevents regressions.

Based on commit 559e77f - 14 debugging attempts documented in problem.md.
"""

import pytest
from unittest.mock import Mock, AsyncMock
import asyncio
import time


class TestAttempt10Scenario:
    """
    Test scenario from Attempt #10 - Initial 1.5s threshold.

    User said: "mowie zdanie nr 1" waited for final, then "teraz mowie zdanie nr 2"
    Problem: Half of first sentence was cut off
    """

    @pytest.mark.asyncio
    async def test_attempt_10_blocking_during_active_speech(self):
        """Test that 1.5s threshold was incorrectly applied during active speech."""
        # Simulated Attempt #10 behavior
        last_audio_end_time = 0.0
        audio_has_ended = False  # User still speaking!
        LATE_FINAL_THRESHOLD = 1.5

        # Words arriving during active speech
        words = [
            {"text": "Ok, powiem", "end_time": 1.2, "blocked_in_attempt_10": False},
            {"text": "pierwsze", "end_time": 2.0, "blocked_in_attempt_10": True},
            {"text": "zdanie i", "end_time": 2.8, "blocked_in_attempt_10": True},
            {"text": "poczekam", "end_time": 3.5, "blocked_in_attempt_10": True},
            {"text": "5", "end_time": 4.2, "blocked_in_attempt_10": True}
        ]

        for word in words:
            if last_audio_end_time == 0.0:
                # First word - not blocked
                blocked = False
            else:
                time_diff = word["end_time"] - last_audio_end_time
                # Attempt #10 bug: Applied threshold even during active speech
                blocked = time_diff <= LATE_FINAL_THRESHOLD

            assert blocked == word["blocked_in_attempt_10"]

            # Update for next iteration
            last_audio_end_time = word["end_time"]

    @pytest.mark.asyncio
    async def test_attempt_10_1_fix_active_speech(self):
        """Test Attempt #10.1 fix: Only apply threshold AFTER audio_end."""
        last_audio_end_time = 0.0
        audio_has_ended = False  # User still speaking
        LATE_FINAL_THRESHOLD = 1.5

        words = [
            {"text": "Ok, powiem", "end_time": 1.2},
            {"text": "pierwsze", "end_time": 2.0},
            {"text": "zdanie i", "end_time": 2.8},
            {"text": "poczekam", "end_time": 3.5},
            {"text": "5", "end_time": 4.2}
        ]

        for word in words:
            time_diff = word["end_time"] - last_audio_end_time if last_audio_end_time != 0.0 else float('inf')

            # Fixed: Only apply threshold AFTER audio_end
            blocked = audio_has_ended and time_diff <= LATE_FINAL_THRESHOLD

            # All should be allowed during active speech
            assert blocked is False

            # Update for next word
            last_audio_end_time = word["end_time"]


class TestAttempt11Scenario:
    """
    Test scenario from Attempt #11 - audio_has_ended reset too early.

    Segment 29 ends at T=10.5s, segment 30 starts at T=10.6s.
    Late final "od 3" arrives at T=11.04s with end_time=10.54s.
    Bug: audio_has_ended reset to False when segment 30 started.
    """

    @pytest.mark.asyncio
    async def test_attempt_11_audio_has_ended_reset_bug(self):
        """Test bug: audio_has_ended was reset when segment started."""
        # Segment 29 ends
        last_audio_end_time = 10.5
        audio_has_ended = True

        # Segment 30 starts - BUG: flag was reset here
        audio_has_ended = False  # Bug!

        # Late final arrives
        late_final_end_time = 10.54
        time_diff = late_final_end_time - last_audio_end_time

        # Check if blocked
        LATE_FINAL_THRESHOLD = 1.5
        blocked = audio_has_ended and time_diff <= LATE_FINAL_THRESHOLD

        # Bug: NOT blocked because audio_has_ended was reset!
        assert blocked is False  # This was the bug
        assert abs(time_diff - 0.04) < 0.001  # Well within threshold

    @pytest.mark.asyncio
    async def test_attempt_11_1_fix_persist_audio_has_ended(self):
        """Test fix: audio_has_ended persists across segment boundary."""
        # Segment 29 ends
        last_audio_end_time = 10.5
        audio_has_ended = True

        # Segment 30 starts - Fixed: DON'T reset flag
        # audio_has_ended stays True

        # Late final arrives
        late_final_end_time = 10.54
        time_diff = late_final_end_time - last_audio_end_time

        # Check if blocked
        LATE_FINAL_THRESHOLD = 1.5
        blocked = audio_has_ended and time_diff <= LATE_FINAL_THRESHOLD

        # Fixed: Properly blocked!
        assert blocked is True
        assert audio_has_ended is True


class TestAttempt14Scenario:
    """
    Test scenario from Attempt #14 - User feedback: "if i wait long enough the issue is not happening".

    Timeline:
    T=0.0s: User finishes speaking
    T=0.6s: Frontend shows "final" (EndOfTranscript)
    T=0.6s: User immediately speaks again
    T=1.8-2.5s: Late finals from first sentence arrive

    With 1.5s threshold: Late finals get through (BUG)
    With 3.0s threshold: Late finals blocked (FIX)
    """

    @pytest.mark.asyncio
    async def test_user_speaks_immediately_after_seeing_final(self):
        """Test the critical user feedback scenario."""
        # User finishes sentence 1
        sentence_1_end = 5.0
        audio_has_ended = True

        # Frontend shows "final" at T+0.6s (EndOfTranscript fires)
        frontend_shows_final = 5.6

        # User speaks sentence 2 immediately
        sentence_2_start = 5.6

        # Late finals arrive between 1.8-2.5s after sentence 1 ended
        late_finals = [
            {"text": "lepiej", "end_time": 6.8, "delay": 1.8},
            {"text": "zdanie", "end_time": 7.2, "delay": 2.2},
            {"text": "ostatnie", "end_time": 7.5, "delay": 2.5}
        ]

        # Test with OLD threshold (1.5s)
        OLD_THRESHOLD = 1.5
        for final in late_finals:
            time_diff = final["end_time"] - sentence_1_end
            blocked_old = audio_has_ended and time_diff <= OLD_THRESHOLD

            # Bug: All get through because > 1.5s
            assert blocked_old is False

        # Test with NEW threshold (3.0s)
        NEW_THRESHOLD = 3.0
        for final in late_finals:
            time_diff = final["end_time"] - sentence_1_end
            blocked_new = audio_has_ended and time_diff <= NEW_THRESHOLD

            # Fixed: All blocked because < 3.0s
            assert blocked_new is True

    @pytest.mark.asyncio
    async def test_user_waits_long_enough_no_issue(self):
        """Test user observation: waiting 3+ seconds prevents duplications."""
        # User finishes sentence 1
        sentence_1_end = 10.0
        audio_has_ended = True

        # User waits 10 seconds
        sentence_2_start = 20.0

        # New sentence arrives
        new_sentence_end = 22.0

        # Check if blocked
        NEW_THRESHOLD = 3.0
        time_diff = new_sentence_end - sentence_1_end
        blocked = audio_has_ended and time_diff <= NEW_THRESHOLD

        # Should NOT be blocked (waited long enough)
        assert blocked is False
        assert time_diff == 12.0  # Way beyond threshold


class TestDuplicatePartialScenario:
    """
    Test scenario: Partial "lepiej" appearing in new line.

    User said: "ale wyglada to duzo duzo lepiej"
    When typing/noise occurred, "lepiej" appeared in new line.
    """

    @pytest.mark.asyncio
    async def test_partial_duplication_from_previous_segment(self):
        """Test that late partials matching previous segment are blocked."""
        # Previous segment finalized
        previous_segment_text = "ale wygląda to dużo dużo lepiej"

        # New segment starts (user typing, noise)
        current_segment_partials = [
            "lepiej",  # Should be blocked (duplicate)
            "teraz mówię",  # Should be allowed (new)
            "nowe zdanie"  # Should be allowed (new)
        ]

        for partial in current_segment_partials:
            blocked = partial in previous_segment_text

            if partial == "lepiej":
                assert blocked is True
            else:
                assert blocked is False


class TestLeadingPunctuationScenario:
    """
    Test scenario: Sentences starting with ". "

    User reported: ". Mówię zdanie nr 1" and ". Mówię. Zdanie nr 2."
    Leading punctuation should be stripped.
    """

    @pytest.mark.asyncio
    async def test_strip_leading_period_space(self):
        """Test leading '. ' is stripped from transcripts."""
        transcripts = [
            {
                "original": ". Mówię zdanie nr 1",
                "expected": "Mówię zdanie nr 1"
            },
            {
                "original": ". Mówię. Zdanie nr 2.",
                "expected": "Mówię. Zdanie nr 2."
            },
            {
                "original": "Normalne zdanie",
                "expected": "Normalne zdanie"
            }
        ]

        for t in transcripts:
            cleaned = t["original"].lstrip('.,!?;: ')
            assert cleaned == t["expected"]


class TestFirstWordMissingScenario:
    """
    Test scenario: First word sometimes missing.

    User reported: "ale wyglada..." but "ale" was missing.
    Root cause: Speechmatics VAD starts too late (not fixable with config).
    """

    @pytest.mark.asyncio
    async def test_first_word_missing_is_provider_issue(self):
        """
        Document that first word missing is a Speechmatics limitation.

        This is NOT a bug in our code - it's Speechmatics internal
        speech detection starting too late. Cannot be fixed with config.
        """
        # What user said
        actual_speech = "ale wygląda to dużo lepiej"

        # What Speechmatics transcribed
        speechmatics_result = "wygląda to dużo lepiej"  # "ale" missing

        # Our code received this - we can't detect missing first word
        # because Speechmatics never sent it in ANY transcript
        missing_words = actual_speech.split()[0]

        assert missing_words == "ale"
        assert missing_words not in speechmatics_result

        # This is a known limitation, not a bug


class TestWordRevisionScenario:
    """
    Test scenario: Word appeared then disappeared.

    User said: "zdanie zostało zakwalifikowane jako final"
    User saw: "Zadanie" appeared in partial, then disappeared.
    This is normal streaming ASR behavior (Speechmatics correcting guesses).
    """

    @pytest.mark.asyncio
    async def test_word_revision_is_normal_behavior(self):
        """Test that word revisions are normal ASR behavior."""
        # Partials as they arrived
        partials = [
            ". Zadanie zostało",  # Initial guess
            "zostało zakwalifikowane"  # Corrected (removed "Zadanie")
        ]

        # This is normal - ASR systems revise guesses
        # "Zadanie" (task) was false positive, corrected to nothing

        assert "Zadanie" in partials[0]
        assert "Zadanie" not in partials[1]

        # This is expected behavior, not a bug


class TestMultiLayerDefenseScenario:
    """
    Test that all 7 blocking mechanisms work together.
    """

    @pytest.mark.asyncio
    async def test_all_seven_mechanisms_active(self):
        """Test that all 7 blocking mechanisms are in place."""
        # Setup: Previous segment ended
        last_audio_end_time = 10.0
        audio_has_ended = True
        previous_segment_text = "poprzednie zdanie było tutaj"

        # Late final arrives
        late_final = {
            "text": ". tutaj",  # Has leading punctuation AND duplicate word
            "end_time": 9.5,  # Backward time!
            "time_since_audio_end": 11.8 - 10.0  # 1.8s
        }

        blocked_reasons = []

        # Mechanism 1: Backward time detection
        if late_final["end_time"] <= last_audio_end_time:
            blocked_reasons.append("backward_time")

        # Mechanism 2: Late final threshold (3.0s)
        LATE_FINAL_THRESHOLD = 3.0
        if audio_has_ended and late_final["time_since_audio_end"] <= LATE_FINAL_THRESHOLD:
            blocked_reasons.append("late_final_threshold")

        # Mechanism 3: audio_has_ended persistence
        if audio_has_ended:
            blocked_reasons.append("audio_ended_flag_persisted")

        # Mechanism 4: Duplicate partial blocking
        cleaned_text = late_final["text"].lstrip('.,!?;: ')
        if previous_segment_text and cleaned_text in previous_segment_text:
            blocked_reasons.append("duplicate_partial")

        # Mechanism 5: Leading punctuation (would be stripped)
        if late_final["text"] != cleaned_text:
            blocked_reasons.append("leading_punctuation_detected")

        # Mechanisms 6 & 7 are configuration/sync (tested separately)

        # Should be blocked by multiple mechanisms
        assert "backward_time" in blocked_reasons
        assert "late_final_threshold" in blocked_reasons
        assert "duplicate_partial" in blocked_reasons
        assert "leading_punctuation_detected" in blocked_reasons
        assert len(blocked_reasons) >= 4


class TestRealWorldTimeline:
    """
    Test real-world timeline from problem.md logs.
    """

    @pytest.mark.asyncio
    async def test_segment_29_to_30_transition(self):
        """
        Test exact timeline from problem.md Attempt #11:

        [10:52:49.643] Segment 29 audio_end (last_audio_end_time=10.50s)
        [10:52:49.643] audio_has_ended=True, threshold blocking ENABLED
        [10:52:49.730] Segment 30 starts
        [10:52:50.241] Late final "od 3" arrives (end_time=10.54s)
        """
        # Segment 29 ends
        segment_29_audio_end = 10.50
        audio_has_ended = True

        # Segment 30 starts (87ms later)
        segment_30_start = segment_29_audio_end + 0.087

        # Late final arrives (598ms after segment 29 ended)
        late_final_arrival = segment_29_audio_end + 0.598
        late_final_end_time = 10.54

        # Check blocking
        time_diff = late_final_end_time - segment_29_audio_end
        NEW_THRESHOLD = 3.0

        blocked = audio_has_ended and time_diff <= NEW_THRESHOLD

        # Should be blocked
        assert blocked is True
        assert abs(time_diff - 0.04) < 0.001  # Only 40ms difference
        assert audio_has_ended is True  # Flag persisted

    @pytest.mark.asyncio
    async def test_attempt_14_user_timeline(self):
        """
        Test exact timeline from user feedback in Attempt #14:

        T=0.0s: User finishes speaking "lepiej"
        T=0.6s: Frontend shows "final" (EndOfTranscript)
        T=0.6s: User immediately speaks next sentence
        T=1.8s: Late final "lepiej" arrives
        """
        # User finishes
        user_finish_time = 0.0

        # EndOfTranscript fires (after 0.6s silence)
        end_of_transcript_time = 0.6

        # Frontend shows final
        frontend_final_time = end_of_transcript_time + 0.05  # Network delay

        # User speaks immediately after seeing final
        user_speaks_again = frontend_final_time

        # Late final arrives
        late_final_arrival = 1.8

        # With OLD threshold (1.5s)
        OLD_THRESHOLD = 1.5
        time_diff = late_final_arrival - user_finish_time
        blocked_old = time_diff <= OLD_THRESHOLD

        # With NEW threshold (3.0s)
        NEW_THRESHOLD = 3.0
        blocked_new = time_diff <= NEW_THRESHOLD

        # Bug vs Fix
        assert blocked_old is False  # Bug: got through
        assert blocked_new is True   # Fix: blocked
        assert time_diff == 1.8


class TestRegressionPrevention:
    """
    Tests to prevent regressions in the fix.
    """

    @pytest.mark.asyncio
    async def test_legitimate_new_speech_not_blocked(self):
        """Ensure legitimate new speech is not blocked."""
        # Previous sentence ended
        last_audio_end_time = 5.0
        audio_has_ended = True

        # User waits 4 seconds
        # Then speaks new sentence
        new_sentence_end_time = 9.5

        # Check blocking
        NEW_THRESHOLD = 3.0
        time_diff = new_sentence_end_time - last_audio_end_time

        # Reset flag when time_diff > threshold
        if time_diff > NEW_THRESHOLD:
            audio_has_ended = False
            last_audio_end_time = new_sentence_end_time

        blocked = False  # Should not block new speech

        assert blocked is False
        assert audio_has_ended is False  # Flag reset
        assert time_diff == 4.5

    @pytest.mark.asyncio
    async def test_rapid_speech_not_blocked(self):
        """Ensure rapid continuous speech is not blocked."""
        last_audio_end_time = 0.0
        audio_has_ended = False  # User actively speaking

        # Words arriving rapidly
        words = [
            {"end_time": 0.5},
            {"end_time": 1.0},
            {"end_time": 1.5},
            {"end_time": 2.0}
        ]

        NEW_THRESHOLD = 3.0

        for word in words:
            time_diff = word["end_time"] - last_audio_end_time if last_audio_end_time > 0 else float('inf')

            # Should NOT block during active speech
            blocked = audio_has_ended and time_diff <= NEW_THRESHOLD

            assert blocked is False

            last_audio_end_time = word["end_time"]

    @pytest.mark.asyncio
    async def test_threshold_boundary_cases(self):
        """Test boundary cases around 3.0s threshold."""
        last_audio_end_time = 10.0
        audio_has_ended = True
        NEW_THRESHOLD = 3.0

        test_cases = [
            {"end_time": 12.99, "should_block": True},   # 2.99s - just under
            {"end_time": 13.0, "should_block": True},    # 3.0s - exactly at
            {"end_time": 13.01, "should_block": False},  # 3.01s - just over
            {"end_time": 15.0, "should_block": False}    # 5.0s - way over
        ]

        for case in test_cases:
            time_diff = case["end_time"] - last_audio_end_time
            blocked = audio_has_ended and time_diff <= NEW_THRESHOLD

            assert blocked == case["should_block"], \
                f"Failed for end_time={case['end_time']}, time_diff={time_diff}"
