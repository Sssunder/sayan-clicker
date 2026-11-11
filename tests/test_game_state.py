"""Unit tests for src.game_state."""

from __future__ import annotations

import random
import unittest

from src import game_state


class GameStateTests(unittest.TestCase):
    def test_levels_definition_and_progression(self) -> None:
        self.assertEqual(len(game_state.LEVELS), 9)
        self.assertEqual(game_state.get_level_info(0).index, 1)
        self.assertEqual(
            game_state.get_level_info(0).title, "Котёнок-первоклассник"
        )
        self.assertEqual(
            game_state.get_level_info(24).title, "Котёнок-первоклассник"
        )
        lvl2 = game_state.get_level_info(25)
        self.assertEqual(lvl2.index, 2)
        self.assertEqual(lvl2.title, "Дежурный по тетрадкам")
        self.assertEqual(lvl2.next_threshold, 75)
        self.assertAlmostEqual(lvl2.progress_ratio, 0.0)

        top = game_state.get_level_info(2500)
        self.assertEqual(top.index, 9)
        self.assertEqual(top.title, "Легендарный Архитектор Уюта")
        self.assertIsNone(top.next_threshold)
        self.assertEqual(top.progress_ratio, 1.0)

    def test_combo_tiers_and_window_reset(self) -> None:
        state = game_state.SayanGameState(_rng=random.Random(42))
        now = 100.0

        # Suppress zoomies auto-trigger for clean combo tier verification, then test zoomies separately
        state.last_zoomies_at = now

        multipliers: list[int] = []
        last_label = ""
        for idx in range(27):
            now += 0.4  # well within 1.4s
            res = state.pet(now=now)
            multipliers.append(res.multiplier)
            last_label = res.multiplier_label

        # Streaks 1..4 -> x1
        self.assertEqual(multipliers[0:4], [1, 1, 1, 1])
        # Streaks 5..11 -> x2
        self.assertEqual(multipliers[4:11], [2] * 7)
        # Streaks 12..24 -> x3
        self.assertEqual(multipliers[11:24], [3] * 13)
        # Streaks 25..27 -> x5
        self.assertEqual(multipliers[24:27], [5, 5, 5])
        self.assertIn("Пятёрочный", last_label)
        self.assertEqual(state.best_combo, 27)

        # Exceed 1.4s combo window -> resets streak to 1
        now += 1.5
        reset_res = state.pet(now=now)
        self.assertEqual(reset_res.combo_streak, 1)
        self.assertEqual(reset_res.multiplier, 1)
        self.assertEqual(state.best_combo, 27)

    def test_sleep_cycle_and_wake_up_bonus(self) -> None:
        state = game_state.SayanGameState(_rng=random.Random(1))
        state.pet(now=10.0)

        # Not idle > 18s yet
        stay_awake = state.tick(now=28.0)
        self.assertFalse(stay_awake.entered_sleep)
        self.assertFalse(state.is_sleeping())

        # Idle > 18s -> enters first sleep pose
        seen_sleep_moods: list[str] = []
        t = 28.5
        for _ in range(4):
            tick_res = state.tick(now=t)
            self.assertTrue(tick_res.entered_sleep)
            self.assertIn(state.mood, game_state.SLEEP_MOODS)
            seen_sleep_moods.append(state.mood)

            # First pet while sleeping wakes up to curious +5 bonus
            before = state.pets_count
            wake_res = state.pet(now=t + 1.0)
            self.assertTrue(wake_res.woke_up)
            self.assertEqual(wake_res.wake_bonus, 5)
            self.assertEqual(wake_res.points_gained, 6)
            self.assertEqual(wake_res.mood, "curious")
            self.assertEqual(wake_res.quote_category, "wake")
            self.assertEqual(state.pets_count, before + 6)
            t += 20.0

        self.assertEqual(len(set(seen_sleep_moods)), 4)

    def test_awake_mood_rotation_and_custom_photo_mode(self) -> None:
        state = game_state.SayanGameState(_rng=random.Random(3))
        state.last_zoomies_at = 0.0

        seen_moods: set[str] = set()
        for step in range(14):
            # Step 2s apart so combo stays 1 (regular mood rotation)
            res = state.pet(now=step * 2.0 + 1.0)
            self.assertIn(res.mood, game_state.AWAKE_MOODS)
            seen_moods.add(res.mood)

        self.assertEqual(seen_moods, set(game_state.AWAKE_MOODS))

        # High combo favors stretch and ambush
        high_combo_moods: list[str] = []
        now = 100.0
        state.last_zoomies_at = now
        for _ in range(16):
            now += 0.2
            res = state.pet(now=now)
            if res.combo_streak >= 10:
                high_combo_moods.append(res.mood)
        stretch_ambush_count = sum(
            1 for m in high_combo_moods if m in ("stretch", "ambush")
        )
        self.assertGreater(stretch_ambush_count, len(high_combo_moods) // 2)

        # Custom photo mode overrides effective sprite while preserving internal mood
        state.set_photo_mode("custom", "C:/SayanClicker/user_photo.png")
        res_custom = state.pet(now=now + 0.2)
        self.assertEqual(res_custom.effective_sprite, game_state.CUSTOM_MOOD)
        self.assertIn(res_custom.mood, game_state.SPRITE_MOODS)

    def test_zoomies_boosts_multiplier_and_expires(self) -> None:
        state = game_state.SayanGameState(_rng=random.Random(7))
        state.trigger_zoomies(now=10.0)

        self.assertTrue(state.is_zoomies_active(now=15.0))
        res = state.pet(now=15.0)
        self.assertEqual(res.mood, "zoomies")
        self.assertTrue(res.zoomies_active)
        self.assertEqual(res.multiplier, 3)  # max(1, 3)

        # Wait past 10s zoomies duration
        tick_res = state.tick(now=20.1)
        self.assertTrue(tick_res.zoomies_ended)
        self.assertFalse(state.is_zoomies_active(now=20.1))
        self.assertNotEqual(state.mood, "zoomies")

    def test_treat_spawn_claim_and_expiration(self) -> None:
        state = game_state.SayanGameState(_rng=random.Random(11))
        state.last_zoomies_at = 0.0

        # Click 14 times spaced 2s apart -> triggers treat on 14th click
        spawned = None
        for idx in range(14):
            res = state.pet(now=10.0 + idx * 2.0)
            if res.spawned_treat is not None:
                spawned = res.spawned_treat
        self.assertIsNotNone(spawned)
        assert spawned is not None
        self.assertIn(spawned.kind, game_state.TREAT_CATALOG)

        before = state.pets_count
        claim = state.claim_treat(now=spawned.spawned_at + 1.0)
        self.assertTrue(claim.claimed)
        self.assertEqual(claim.points_gained, spawned.bonus)
        self.assertEqual(state.pets_count, before + spawned.bonus)
        self.assertEqual(state.total_events_caught, 1)
        self.assertIsNone(state.active_treat)

        # Spawn another treat and let it expire
        expired_treat = state.spawn_treat(kind="five", now=100.0)
        self.assertEqual(expired_treat.bonus, 25)
        late_claim = state.claim_treat(now=110.0)
        self.assertFalse(late_claim.claimed)
        self.assertEqual(late_claim.points_gained, 0)
        self.assertIsNone(state.active_treat)

    def test_math_micro_quiz_bank_and_scoring(self) -> None:
        self.assertGreaterEqual(len(game_state.MATH_QUIZ_BANK), 12)
        state = game_state.SayanGameState(_rng=random.Random(5))

        for idx, quiz in enumerate(game_state.MATH_QUIZ_BANK):
            self.assertEqual(len(quiz.options), 3)
            self.assertIn(quiz.correct_index, (0, 1, 2))
            spawned = state.spawn_quiz(index=idx)
            self.assertEqual(spawned.question, quiz.question)

            before = state.pets_count
            solved_before = state.quizzes_solved
            res = state.answer_quiz(quiz.correct_index, now=10.0 + idx)
            self.assertTrue(res.correct)
            self.assertEqual(res.points_gained, 30)
            self.assertEqual(state.pets_count, before + 30)
            self.assertEqual(state.quizzes_solved, solved_before + 1)

        # Wrong answer yields 0 without penalty or solved increment
        quiz = state.spawn_quiz(index=0)
        wrong_idx = (quiz.correct_index + 1) % 3
        before = state.pets_count
        solved_before = state.quizzes_solved
        wrong_res = state.answer_quiz(wrong_idx, now=99.0)
        self.assertFalse(wrong_res.correct)
        self.assertEqual(wrong_res.points_gained, 0)
        self.assertEqual(state.pets_count, before)
        self.assertEqual(state.quizzes_solved, solved_before)

    def test_milestones_and_pi_314_easter_egg(self) -> None:
        state = game_state.SayanGameState(pets_count=310)
        state.unlocked_milestones = [1, 5, 25, 50, 100, 150]
        state.spawn_quiz(index=0)
        res = state.answer_quiz(state.active_quiz.correct_index, now=50.0)
        self.assertEqual(state.pets_count, 340)
        self.assertIn(314, res.new_milestones)
        self.assertIn(314, state.unlocked_milestones)
        self.assertIn("Пи-Мурр", res.quote)

        # Also verify direct pet() crossing 314 triggers Пи-Мурр
        state2 = game_state.SayanGameState(pets_count=313)
        state2.unlocked_milestones = [1, 5, 25, 50, 100, 150]
        pet_res = state2.pet(now=10.0)
        self.assertEqual(state2.pets_count, 314)
        self.assertEqual(pet_res.new_milestones, (314,))
        self.assertIn("Пи-Мурр", pet_res.quote)

    def test_auto_zoomies_on_high_combo_and_tick_treat_spawn(self) -> None:
        state = game_state.SayanGameState(_rng=random.Random(9))
        started = False
        now = 10.0
        for _ in range(15):
            now += 0.3
            res = state.pet(now=now)
            if res.zoomies_started:
                started = True
        self.assertTrue(started)
        self.assertTrue(state.is_zoomies_active(now=now))
        self.assertEqual(state.mood, "zoomies")

        # Tick treat spawn when awake and interval elapsed
        state2 = game_state.SayanGameState(_rng=random.Random(9))
        state2.tick(now=0.0)
        state2.pet(now=15.0)  # keep awake past 28s mark
        tick_res = state2.tick(now=29.0)
        self.assertFalse(tick_res.entered_sleep)
        self.assertIsNotNone(tick_res.spawned_treat)

    def test_quotes_categories_and_config_roundtrip(self) -> None:
        expected_categories = (
            "pet",
            "math_easter_egg",
            "combo",
            "sleep",
            "wake",
            "treat",
            "zoomies",
            "quiz_win",
            "milestone",
        )
        for cat in expected_categories:
            self.assertIn(cat, game_state.CAT_QUOTES)
            self.assertGreater(len(game_state.CAT_QUOTES[cat]), 0)

        cfg = {
            "pets_count": 88,
            "best_combo": 19,
            "total_events_caught": 4,
            "quizzes_solved": 2,
            "active_photo_mode": "auto",
            "custom_photo_path": None,
            "unlocked_milestones": [1, 5, 25, 50],
        }
        state = game_state.SayanGameState.from_config(cfg)
        self.assertEqual(state.pets_count, 88)
        self.assertEqual(state.best_combo, 19)
        self.assertEqual(state.to_config_updates(), cfg)


if __name__ == "__main__":
    unittest.main()
