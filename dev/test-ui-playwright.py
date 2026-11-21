import os
import sys
from playwright.sync_api import sync_playwright

def test_sayan_ui():
    html_path = os.path.abspath("docs/index.html")
    file_url = f"file:///{html_path.replace(os.sep, '/')}"
    print(f"Loading {file_url}...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        # Listen for console errors
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        page.goto(file_url)
        page.wait_for_timeout(1000)

        # If grade overlay is open on first run, pick grade 0 (Mix)
        if page.locator("#gradeOverlay").is_visible():
            print("Grade overlay opened on first run, choosing Mix...")
            page.locator("#gradeMix").click()
            page.wait_for_timeout(500)

        # 1. Verify Sayan is visible at the top of column 1
        stage_box = page.locator("#stage").bounding_box()
        assert stage_box is not None, "Stage is missing"
        assert stage_box["y"] < 120, f"Stage is too low: y={stage_box['y']} (Sayan must be at the top!)"
        print(f"✓ Sayan is front and center at y={stage_box['y']}")

        # Verify top-score-badge is in topbar
        top_score = page.locator("#topScore").inner_text()
        print(f"✓ Topbar score visible: {top_score}")

        # 2. Test Space key (petting Sayan)
        score_before = int(page.locator("#score").inner_text().replace(" ", "").replace("\xa0", ""))
        page.keyboard.press("Space")
        page.wait_for_timeout(300)
        score_after = int(page.locator("#score").inner_text().replace(" ", "").replace("\xa0", ""))
        assert score_after > score_before, f"Score did not increase on Space: {score_before} -> {score_after}"
        print(f"✓ Space key successfully petted Sayan ({score_before} -> {score_after} paws)")

        # 3. Test Q key (spawn quiz)
        page.keyboard.press("q")
        page.wait_for_timeout(300)
        assert page.locator("#quizCard").is_visible(), "Quiz card did not open on Q"
        quiz_box = page.locator("#quizCard").bounding_box()
        assert quiz_box["y"] >= stage_box["y"], "Quiz should appear below Sayan"
        print(f"✓ Q key opened quiz card below Sayan (y={quiz_box['y']})")
        page.screenshot(path="dev/screenshots/quiz_open.png")
        print("✓ Saved dev/screenshots/quiz_open.png")

        # 4. Test 1, 2, 3 hotkeys
        # Click button to set focus on a button first (to prove buttons don't block hotkeys anymore!)
        page.locator("#hintBtn").focus()
        page.wait_for_timeout(100)
        page.keyboard.press("1")
        page.wait_for_timeout(400)
        feedback = page.locator("#quizFeedback")
        assert feedback.is_visible(), "Quiz was not answered with digit key '1'"
        print(f"✓ Digit key '1' answered quiz! Feedback: '{feedback.inner_text()}'")

        # Close quiz with Escape
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)

        # 5. Test Secret Album and Secret View (Image #1 issue)
        page.locator("#secretBtn").click()
        page.wait_for_timeout(400)
        assert page.locator("#secretOverlay").is_visible(), "Secret overlay did not open"

        # Trigger secret view via JS (simulating unlocking/opening secret 1)
        page.evaluate("openSecret(1)")
        page.wait_for_timeout(500)
        assert page.locator("#secretView").is_visible(), "Secret view did not open"

        # Check background and styling of secret view
        bg_color = page.evaluate("window.getComputedStyle(document.getElementById('secretView')).backgroundColor")
        card_bg = page.evaluate("window.getComputedStyle(document.querySelector('.secret-view-card')).backgroundColor")
        print(f"✓ Secret view backdrop: {bg_color}, card background: {card_bg}")
        assert "rgba(0, 0, 0, 0)" not in bg_color, "Secret view backdrop is transparent!"

        # Take screenshot of the secret view modal
        os.makedirs("dev/screenshots", exist_ok=True)
        page.screenshot(path="dev/screenshots/secret_view.png")
        print("✓ Saved dev/screenshots/secret_view.png")

        # Close secret view
        page.locator("#secretViewClose").click()
        page.wait_for_timeout(300)
        assert not page.locator("#secretView").is_visible(), "Secret view did not close"

        # Close secret overlay
        page.locator("#secretClose").click()
        page.wait_for_timeout(300)

        # Take screenshot of main game screen
        page.screenshot(path="dev/screenshots/main_game.png")
        print("✓ Saved dev/screenshots/main_game.png")

        print("ALL PLAYWRIGHT UI TESTS PASSED!")
        browser.close()

if __name__ == "__main__":
    test_sayan_ui()
