# Day 32 — CV Detection Testing Plan

**Assignee:** Shavi  
**Date:** 2026-11-03  
**Component:** Computer Vision Detection Pipeline  
**Environment:** FocusLens Desktop Application (React + TypeScript + Tauri + Python + OpenCV + MediaPipe)

---

## Executive Summary

This document provides a comprehensive testing plan for the FocusLens computer-vision detection pipeline. Since automated testing cannot verify real-world environmental conditions (lighting, camera positioning, background), this plan focuses on **manual webcam testing** combined with **programmatic edge-case verification**.

**Scope:**
- Person-presence detection
- Away detection
- Screen-facing estimation
- Posture detection
- Error handling and recovery
- Privacy verification (no data leaves local device)

---

## Current CV Architecture Summary

### Detection Components

| Component | Service | Key Thresholds | Stability Mechanism |
|-----------|---------|----------------|-------------------|
| Person Presence | `PresenceReliabilityTracker` | 3 consecutive detections → PRESENT, 5 consecutive missing → AWAY, 3 consecutive unknown → UNKNOWN | Consecutive-frame tracking |
| Screen Facing | `ScreenFacingEstimator` + `ScreenFacingReliabilityTracker` | Yaw ratio ≤ 0.20, Nose vertical 0.20–0.80, Min confidence 0.15 | 3 consecutive frames to switch states |
| Posture | `PostureClassifier` + `PostureReliabilityTracker` | Ear-shoulder ratio ≥ 0.55 → GOOD, < 0.35 → SLOUCHED, Dead zone in between | 3 consecutive frames to switch states |

### Configuration Values

**From `cv/config/settings.py`:**
- Camera: 640x480 @ 30 FPS
- Face detection confidence: 0.5
- Pose detection confidence: 0.5
- Max faces/poses: 1 (single user tracking)

**From `cv/config/stability.py`:**
- Presence detection threshold: 3 frames
- Presence missing threshold: 5 frames
- Screen-facing consecutive threshold: 3 frames
- Posture consecutive threshold: 3 frames
- Posture ear-shoulder good threshold: 0.55
- Posture ear-shoulder slouch threshold: 0.35
- Posture max shoulder tilt: 0.25

---

## Test Environment Setup

### Prerequisites
1. FocusLens application running with CV pipeline active
2. Webcam available and functional
3. Dev preview enabled (`SHOW_DEV_PREVIEW = True` in `cv/config/settings.py`)
4. Test recording method (screen capture or notes)

### Test Environment Notes
Record the following for each test scenario:
- Date/time
- Lighting condition
- Camera position/distance
- Background description
- User position/posture

---

## Test Scenarios

### 1. Lighting Conditions

#### 1.1 Bright Lighting
**Environment:**
- Bright room lighting or direct sunlight (not on camera lens)
- Well-lit face and upper body

**Expected Result:**
- Face landmarks detected reliably
- Person presence: PRESENT
- Screen-facing: SCREEN_FACING when facing screen
- Posture: GOOD_POSTURE when sitting upright

**Test Steps:**
1. Start CV pipeline
2. Sit in front of camera in normal upright posture
3. Observe person presence, screen-facing, and posture states
4. Record stability and any flickering

**Pass Criteria:**
- Person presence detected as PRESENT within 3–5 seconds
- Screen-facing shows SCREEN_FACING when facing forward
- Posture shows GOOD_POSTURE when upright
- No rapid state switching

---

#### 1.2 Normal Indoor Lighting
**Environment:**
- Standard office or home lighting
- No direct sunlight or bright backlight

**Expected Result:**
- Consistent detection similar to bright lighting
- Slightly lower confidence but still reliable

**Test Steps:**
1. Start CV pipeline
2. Sit in normal position
3. Observe detection states
4. Note any differences from bright lighting

**Pass Criteria:**
- All detection states behave correctly
- Confidence values remain acceptable (> 0.5)

---

#### 1.3 Low Lighting
**Environment:**
- Dim room lighting
- Face and upper body visible but less contrast

**Expected Result:**
- Detection may be less reliable
- Lower confidence values
- Possible UNKNOWN states when lighting is too low

**Test Steps:**
1. Reduce room lighting
2. Observe detection states
3. Note confidence values (check dev preview overlay)
4. Test whether detection recovers when lighting improves

**Pass Criteria:**
- System falls back to UNKNOWN gracefully rather than false positives
- Detection recovers when lighting improves
- No crashes or application errors

---

#### 1.4 Uneven Lighting
**Environment:**
- Strong light from one side (e.g., window)
- Half face in shadow

**Expected Result:**
- Face may still be detected but with lower confidence
- Posture may be affected if landmarks are asymmetric

**Test Steps:**
1. Position near a window with strong side lighting
2. Turn face toward and away from light source
3. Observe detection states
4. Note any false detections or instability

**Pass Criteria:**
- System does not crash with uneven lighting
- States transition reasonably (may have UNKNOWN moments)
- No persistent false positives

---

#### 1.5 Backlighting (Light from Behind)
**Environment:**
- Camera facing a bright window or light source
- User between camera and light

**Expected Result:**
- Face may appear silhouetted
- Detection may fail or have very low confidence

**Test Steps:**
1. Position camera facing a bright window
2. Sit between camera and window
3. Observe detection
4. Try adjusting position to avoid backlight

**Pass Criteria:**
- Graceful degradation to UNKNOWN when detection impossible
- No false positives in impossible conditions
- Application remains stable

---

### 2. Camera Positioning

#### 2.1 Camera at Eye Level
**Environment:**
- Camera positioned at user's eye level
- Straight-on angle

**Expected Result:**
- Optimal detection
- Reliable screen-facing estimation
- Accurate posture classification

**Test Steps:**
1. Position webcam at eye level, 2–3 feet away
2. Sit in normal upright posture
3. Observe all detection states
4. Turn head left/right slightly and observe screen-facing changes

**Pass Criteria:**
- Person presence: PRESENT
- Screen-facing: SCREEN_FACING when facing forward, LOOKING_AWAY when turning head
- Posture: GOOD_POSTURE when upright
- Smooth state transitions

---

#### 2.2 Camera Slightly Above Eye Level
**Environment:**
- Camera positioned 10–15 degrees above eye level
- Looking down at camera

**Expected Result:**
- Face still detectable
- Posture may be affected (head tilted down)

**Test Steps:**
1. Place camera above monitor, angled down
2. Sit in normal posture
3. Observe detection states
4. Try different head orientations

**Pass Criteria:**
- Detection still functional
- Posture may show SLOUCHED due to head angle (this is a limitation)
- No crashes

---

#### 2.3 Camera Slightly Below Eye Level
**Environment:**
- Camera positioned 10–15 degrees below eye level
- Looking up at camera

**Expected Result:**
- Face still detectable
- Screen-facing may be affected

**Test Steps:**
1. Place camera below monitor, angled up
2. Sit in normal posture
3. Observe detection states

**Pass Criteria:**
- Detection functional
- Screen-facing may show LOOKING_AWAY even when facing screen (angle limitation)
- Stable person presence

---

#### 2.4 Camera at an Angle
**Environment:**
- Camera positioned 30–45 degrees off-center
- Not directly in front of user

**Expected Result:**
- Face detection may still work but with lower confidence
- Posture classification may fail (shoulder tilt threshold)
- Screen-facing may be inaccurate

**Test Steps:**
1. Place camera at 45-degree angle
2. Sit in normal posture
3. Observe all detection states
4. Note which components fail

**Pass Criteria:**
- Person presence should still work (face still visible)
- Posture may correctly fall back to UNKNOWN due to shoulder tilt
- No false positives

---

#### 2.5 Camera at Different Distances
**Environment:**
- Close: 1–2 feet from camera
- Normal: 2–3 feet from camera
- Far: 4–5 feet from camera

**Expected Result:**
- Posture detection should be scale-invariant (ratio-based)
- Very close or very far may affect landmark accuracy

**Test Steps:**
1. Test at 2 feet, 3 feet, and 4 feet
2. For each distance, test upright and slouched posture
3. Observe posture classification
4. Note at which distance posture becomes unreliable

**Pass Criteria:**
- Posture should work correctly at normal distances (2–3 feet)
- May degrade at extreme distances
- No crashes at any distance

---

### 3. User Positioning and Movement

#### 3.1 Sitting Directly in Front
**Environment:**
- User centered in camera frame
- Normal upright posture

**Expected Result:**
- All detection components working optimally
- High confidence

**Test Steps:**
1. Center in camera frame
2. Maintain upright posture
3. Observe states for 10–15 seconds
4. Check for stability

**Pass Criteria:**
- PRESENT, SCREEN_FACING, GOOD_POSTURE all stable
- No flickering

---

#### 3.2 Moving Slightly Away
**Environment:**
- Start centered, then lean back 6–12 inches
- Remain in camera frame

**Expected Result:**
- Person should remain PRESENT
- Posture may change if body angle changes

**Test Steps:**
1. Start centered, upright
2. Lean back in chair
3. Observe states
4. Return to original position
5. Verify recovery

**Pass Criteria:**
- Person remains PRESENT (no false AWAY)
- Posture updates appropriately if angle changes
- States recover when returning to original position

---

#### 3.3 Turning Head Left or Right
**Environment:**
- User turns head 30–45 degrees left or right
- Body remains facing screen

**Expected Result:**
- Person: PRESENT (face still visible)
- Screen-facing: LOOKING_AWAY (correctly identifies head turn)
- Posture: UNKNOWN or remains GOOD (depending on ear visibility)

**Test Steps:**
1. Start facing screen
2. Turn head 45 degrees left
3. Observe screen-facing state
4. Return to center
5. Repeat to the right
6. Verify screen-facing recovers

**Pass Criteria:**
- Person remains PRESENT
- Screen-facing shows LOOKING_AWAY when head turned
- Screen-facing recovers to SCREEN_FACING when facing forward
- No false AWAY states

---

#### 3.4 Looking Down or Up
**Environment:**
- User looks down (at keyboard/book) or up (at ceiling)
- Body position unchanged

**Expected Result:**
- Person: PRESENT (face still visible)
- Screen-facing: LOOKING_AWAY when looking down
- Posture: May show SLOUCHED when looking down (head position)

**Test Steps:**
1. Start facing screen upright
2. Look down at keyboard for 5 seconds
3. Observe screen-facing and posture
4. Look up at ceiling
5. Observe changes
6. Return to normal

**Pass Criteria:**
- Person remains PRESENT
- Screen-facing shows LOOKING_AWAY when not facing screen
- Posture state changes appropriately based on head position
- Recovery when returning to normal

---

#### 3.5 Temporarily Leaving Camera View
**Environment:**
- User stands up and walks out of frame
- Camera sees empty room or background

**Expected Result:**
- Person: AWAY after 5 consecutive missing frames (~0.17 seconds at 30 FPS)
- Screen-facing: UNKNOWN
- Posture: UNKNOWN

**Test Steps:**
1. Start with user in frame
2. Confirm PRESENT state
3. Stand up and walk out of frame
4. Observe AWAY transition
5. Return to frame
6. Observe recovery to PRESENT

**Pass Criteria:**
- AWAY triggers within ~0.2 seconds after leaving frame
- PRESENT recovers within ~0.1 seconds after returning
- No false AWAY when user is in frame
- No crashes during transitions

---

#### 3.6 Returning After Being Away
**Environment:**
- User leaves frame, then returns
- Test different return angles and speeds

**Expected Result:**
- Detection recovers smoothly
- No lag or instability after return

**Test Steps:**
1. Leave frame (trigger AWAY)
2. Return from different angles (left, right, slightly off-center)
3. Observe recovery time and state
4. Repeat rapid away/return cycles

**Pass Criteria:**
- PRESENT recovers within 3–5 frames (~0.1–0.17 seconds)
- Screen-facing and posture recover within ~0.5–1 second
- No instability after rapid away/return cycles

---

#### 3.7 Changing Posture
**Environment:**
- User transitions between upright and slouched posture
- Test intentional posture changes

**Expected Result:**
- Posture transitions between GOOD_POSTURE and SLOUCHED
- Takes 3 consecutive frames to switch (debounce)
- No flickering at decision boundaries

**Test Steps:**
1. Start in upright posture
2. Slouch intentionally (lean forward, hunch shoulders)
3. Observe posture state change (should take ~0.1–0.2 seconds)
4. Return to upright
5. Observe recovery
6. Test rapid posture changes every 2–3 seconds

**Pass Criteria:**
- Posture changes to SLOUCHED after ~3 frames of slouching
- Returns to GOOD_POSTURE after ~3 frames of upright
- No flickering at boundary (dead zone between thresholds)
- Rapid changes debounced appropriately

---

### 4. Background Conditions

#### 4.1 Simple Background
**Environment:**
- Plain wall or curtain behind user
- No movement or clutter

**Expected Result:**
- Optimal detection conditions
- No false detections from background

**Test Steps:**
1. Position with simple background
2. Test all detection components
3. Observe for 1–2 minutes

**Pass Criteria:**
- All components work correctly
- No false detections from background
- Stable states

---

#### 4.2 Cluttered Background
**Environment:**
- Bookshelf, plants, or objects behind user
- Some movement possible (fans, people in background)

**Expected Result:**
- Should not affect detection (MediaPipe is person-focused)
- No false positives from background objects

**Test Steps:**
1. Position with cluttered background
2. Test normal posture and movements
3. Observe detection stability
4. Introduce background movement (e.g., person walking behind)

**Pass Criteria:**
- Detection unaffected by clutter
- No false person presence from background objects
- Background movement does not trigger state changes

---

#### 4.3 Movement Behind User
**Environment:**
- Another person walking behind the user
- Background activity while user is focused

**Expected Result:**
- Should not affect detection (foreground tracking)
- No false away states

**Test Steps:**
1. Have someone walk behind you while you're in frame
2. Maintain focus on screen
3. Observe person presence and screen-facing states
4. Test multiple passes

**Pass Criteria:**
- No false AWAY when background person walks by
- No false posture changes
- Detection remains focused on primary user

---

#### 4.4 Other People in Background
**Environment:**
- Other people visible in camera frame (background)
- Primary user remains in foreground

**Expected Result:**
- MediaPipe should track primary/nearest face
- No confusion between users

**Test Steps:**
1. Have another person stand behind or beside you
2. Confirm you're still detected as the primary user
3. Other person moves while you remain still
4. Observe if your detection is affected

**Pass Criteria:**
- Your detection remains stable
- No false states triggered by background person
- Max faces setting (1) prevents confusion

---

### 5. Detection Reliability Verification

#### 5.1 Person-Presence Detection

**Sub-scenarios:**
- Confirm PRESENT when user is in frame
- Confirm AWAY when user leaves frame
- Verify no false AWAY when user is in frame
- Verify no false PRESENT when frame is empty

**Test Steps:**
1. Test AWAY by leaving frame for 5 seconds
2. Return and verify PRESENT recovery
3. Stay in frame for 2 minutes to check for false AWAY
4. Cover camera briefly and verify AWAY triggers

**Pass Criteria:**
- AWAY only when genuinely away
- PRESENT when user is visible
- No false transitions during 2-minute stable test

---

#### 5.2 Away Detection

**Sub-scenarios:**
- Timely AWAY trigger when leaving frame
- Timely PRESENT recovery when returning
- No false AWAY during session

**Test Steps:**
1. Measure time from leaving frame to AWAY state (should be ~0.17s)
2. Measure time from returning to PRESENT (should be ~0.1s)
3. Stay in frame for 2 minutes, check for false AWAY

**Pass Criteria:**
- AWAY triggers within 5 frames (~0.17s)
- PRESENT recovers within 3 frames (~0.1s)
- Zero false AWAY events during 2-minute test

---

#### 5.3 Screen-Facing Estimation

**Sub-scenarios:**
- SCREEN_FACING when facing screen
- LOOKING_AWAY when head turned
- Recovery when returning to face screen
- No false classifications

**Test Steps:**
1. Facing screen: should be SCREEN_FACING
2. Turn head 45° left: should be LOOKING_AWAY
3. Return to center: should recover to SCREEN_FACING
4. Repeat to right
5. Test small head turns (15°) – may still be SCREEN_FACING
6. Test looking down at keyboard – should be LOOKING_AWAY

**Pass Criteria:**
- SCREEN_FACING when facing forward within ±15°
- LOOKING_AWAY for turns >30°
- Smooth recovery when returning to center
- No flickering between states

---

#### 5.4 Posture Detection

**Sub-scenarios:**
- GOOD_POSTURE when sitting upright
- SLOUCHED when leaning forward/hunching
- UNKNOWN when landmarks missing or ambiguous
- No false posture events

**Test Steps:**
1. Upright posture: should be GOOD_POSTURE
2. Slouch (lean forward, hunch shoulders): should be SLOUCHED
3. Return to upright: should recover to GOOD_POSTURE
4. Turn head sideways: may fall to UNKNOWN (ears not visible)
5. Rapid posture changes: should debounce (no flickering)
6. Edge case: extreme forward lean – may still be SLOUCHED

**Pass Criteria:**
- GOOD_POSTURE when upright with ears above shoulders
- SLOUCHED when head drops toward shoulders
- UNKNOWN when landmarks are invalid
- No flickering at boundaries (dead zone prevents this)
- Recovery when returning to valid posture

---

### 6. False Detection and Recovery Investigation

#### 6.1 Temporary Landmark Detection Failures

**Test Scenarios:**
- Brief occlusion (hand over face)
- Camera blur (motion during movement)
- Face partially out of frame

**Expected Result:**
- Falls back to UNKNOWN rather than false state
- Recovers when landmarks return
- No persistent false positives

**Test Steps:**
1. Briefly cover face with hand (1–2 seconds)
2. Observe state change to UNKNOWN
3. Remove hand and observe recovery
4. Move head quickly to cause motion blur
5. Sit partially out of frame
6. Verify recovery in all cases

**Pass Criteria:**
- Falls to UNKNOWN during occlusion/blur
- Recovers to correct state when landmarks return
- No false AWAY or false SLOUCHED during transient issues

---

#### 6.2 Incorrect Person-Present or Away Transitions

**Test Scenarios:**
- False AWAY when user is clearly present
- False PRESENT when frame is empty
- Flickering between states

**Expected Result:**
- Debounce thresholds prevent flickering
- Reliable transitions only

**Test Steps:**
1. Stay in frame for 2 minutes, monitor for any AWAY triggers
2. Leave frame for 1 second, verify AWAY triggers
3. Return quickly, verify PRESENT recovers
4. Repeat rapid away/return cycles 10 times

**Pass Criteria:**
- Zero false AWAY events during 2-minute stable test
- Rapid away/return cycles handled correctly
- No state flickering

---

#### 6.3 Repeated State Changes (Instability)

**Test Scenarios:**
- Sitting at decision boundary (e.g., posture threshold)
- Small movements that could trigger state changes
- Head movements that could trigger screen-facing changes

**Expected Result:**
- Dead zones prevent boundary flickering
- Debounce thresholds prevent rapid switching
- Stable states once achieved

**Test Steps:**
1. Find posture boundary (slouch slightly, then return)
2. Hover at boundary for 10 seconds
3. Observe if state flickers
4. Find screen-facing boundary (small head turns)
5. Hover at boundary
6. Observe if state flickers

**Pass Criteria:**
- No flickering at posture boundary (dead zone works)
- No flickering at screen-facing boundary (debounce works)
- States remain stable at boundaries

---

#### 6.4 False Posture Events

**Test Scenarios:**
- GOOD_POSTURE when actually slouched
- SLOUCHED when actually upright
- Posture changing when person is AWAY

**Expected Result:**
- Posture should be UNKNOWN when person is AWAY
- Accurate classification at boundaries
- No false positives

**Test Steps:**
1. Leave frame, observe posture state (should be UNKNOWN)
2. Slouch while AWAY, return, observe (should be UNKNOWN until in frame)
3. Test upright posture at different distances
4. Test slouched posture at different distances
5. Verify classification accuracy

**Pass Criteria:**
- Posture is UNKNOWN when person is AWAY (correct)
- Posture classification accurate at normal distances
- No false positives at boundaries (dead zone prevents this)

---

#### 6.5 Incorrect Screen-Facing Classifications

**Test Scenarios:**
- SCREEN_FACING when head is turned away
- LOOKING_AWAY when facing screen
- Classification affected by camera angle

**Expected Result:**
- Accurate classification for head turns
- May have limitations with extreme camera angles

**Test Steps:**
1. Test head turns at different angles (15°, 30°, 45°, 60°)
2. Identify threshold where LOOKING_AWAY triggers
3. Test with camera at different angles (2.1, 2.2, 2.3)
4. Note any false classifications

**Pass Criteria:**
- LOOKING_AWAY triggers for turns >30°
- SCREEN_FACING for turns <15°
- Reasonable behavior at 20–30° (may vary with camera setup)
- Document any angle-specific limitations

---

#### 6.6 Detection Failures That Do Not Recover

**Test Scenarios:**
- Face disappears and doesn't return
- Landmarks not detected after valid input
- State stuck in AWAY/UNKNOWN

**Expected Result:**
- All recoverable scenarios should recover
- Only truly unavailable input stays in UNKNOWN

**Test Steps:**
1. Cover face completely, remove, verify recovery
2. Turn off room lights, turn on, verify recovery
3. Move to edge of frame, return to center, verify recovery
4. Test after rapid movements

**Pass Criteria:**
- All recoverable scenarios recover within 1 second
- Only truly unavailable input stays in UNKNOWN
- No stuck states requiring restart

---

## Programmatic Edge-Case Tests

These tests can be run without a webcam to verify boundary conditions and error handling.

### Test Categories

1. **Invalid/Edge Confidence Values**
   - Confidence = 0.0, 0.5, 1.0, -1.0, 2.0
   - Confidence thresholds exactly at boundaries

2. **Invalid Landmark Data**
   - Missing landmarks
   - NaN/infinite landmark coordinates
   - Degenerate geometry (overlapping shoulders)

3. **Threshold Boundary Tests**
   - Ear-shoulder ratio at exact thresholds (0.35, 0.55)
   - Screen-facing yaw ratio at threshold (0.20)
   - Consecutive frame counts at thresholds (3, 5)

4. **State Transition Tests**
   - AWAY → PRESENT recovery
   - UNKNOWN → PRESENT/AWAY transitions
   - Posture state transitions at boundaries

5. **Error Handling**
   - Empty frame input
   - None frame input
   - Corrupted frame data
   - Model unavailable

---

## Testing Report Template

For each test scenario, record:

| Scenario | Environment | Expected Result | Actual Result | Pass/Fail | Observed Problem | Fix Applied | Remaining Limitations |
|----------|------------|----------------|---------------|----------|-----------------|------------|---------------------|
| | | | | | | | | |

**Test Execution Notes:**
- Date/time of test
- Tester name
- Software version (git commit)
- Hardware specs (camera model, resolution)

---

## Privacy Verification

### Test: No Data Leaves Local Device

**Verification Steps:**
1. Monitor network traffic during CV operation (no uploads should occur)
2. Check logs for any network requests
3. Verify stdout only contains JSON signals (no frame data)
4. Confirm no raw images saved to disk

**Expected Result:**
- Zero network traffic during CV operation
- Only metadata (states, confidence) emitted via stdout
- No raw frames stored or transmitted

**Pass Criteria:**
- No network traffic detected
- Signal JSON contains only metadata keys
- No frame/image data in signal output

---

## Regression Testing Plan

After any code changes:

1. **Re-test person-presence detection**
   - AWAY trigger timing
   - PRESENT recovery timing
   - False AWAY rate

2. **Re-test away detection**
   - Integration with session timer
   - Activity event generation

3. **Re-test screen-facing estimation**
   - Head turn detection
   - Recovery behavior

4. **Re-test posture detection**
   - Upright vs slouched classification
   - Boundary behavior

5. **Verify CV pipeline connection to activity-event pipeline**
   - Signals flow correctly to frontend
   - Activity events generated for state changes

6. **Run existing CV tests**
   - `cv/tests/test_detection_state_integration.py`
   - `cv/tests/test_posture_classifier.py`
   - `cv/tests/test_posture_integration.py`
   - `cv/tests/test_screen_facing_reliability.py`
   - `tests/cvDesktopIntegration.test.ts`

---

## Remaining CV Limitations (Based on Architecture)

1. **Camera Angle Sensitivity**
   - Screen-facing and posture are sensitive to camera angle
   - Extreme angles (>45°) may produce UNKNOWN states
   - This is inherent to the geometric approach

2. **Distance Sensitivity**
   - Very close (<2 ft) or very far (>5 ft) may reduce accuracy
   - Scale-invariant posture helps but has limits

3. **Lighting Sensitivity**
   - Very low lighting or extreme backlighting may fail detection
   - System gracefully degrades to UNKNOWN

4. **Side Profile Limitations**
   - Head turned >60° may result in UNKNOWN posture (ears not visible)
   - This is by design (ears not available → UNKNOWN)

5. **Approximate Classification**
   - Screen-facing and posture are estimates, not medical measurements
   - Thresholds are initial estimates and may need calibration

---

## Next Steps

1. **Execute manual webcam tests** using this plan
2. **Document results** in the Testing Report Template
3. **Run programmatic edge-case tests** (to be implemented)
4. **Analyze results** and identify necessary fixes
5. **Apply targeted fixes** (threshold adjustments, logic improvements)
6. **Perform regression testing** after fixes
7. **Update this plan** based on findings
