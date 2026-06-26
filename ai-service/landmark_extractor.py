import cv2
import mediapipe as mp
import csv
import os

# ----------------------------
# MediaPipe Hands
# ----------------------------
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)

# ----------------------------
# Webcam
# ----------------------------
cap = cv2.VideoCapture(0)

csv_file = "landmarks.csv"

# Create CSV header if file doesn't exist
if not os.path.exists(csv_file):

    header = ["label"]

    for i in range(21):
        header.append(f"x{i}")
        header.append(f"y{i}")
        header.append(f"z{i}")

    with open(csv_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)

print("\n")
print("===================================")
print("Press S  -> Save current landmarks")
print("Press Q  -> Quit")
print("===================================")
print("\n")

label = "UNKNOWN"

while True:

    ret, frame = cap.read()

    if not ret:
        break

    frame = cv2.flip(frame, 1)

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    results = hands.process(rgb)

    row = None

    if results.multi_hand_landmarks:

        for hand_landmarks in results.multi_hand_landmarks:

            mp_draw.draw_landmarks(
                frame,
                hand_landmarks,
                mp_hands.HAND_CONNECTIONS,
            )

            row = [label]

            print("\n----------- NEW FRAME -----------")

            for idx, lm in enumerate(hand_landmarks.landmark):

                print(
                    f"{idx:02d} : "
                    f"x={lm.x:.4f} "
                    f"y={lm.y:.4f} "
                    f"z={lm.z:.4f}"
                )

                row.extend([lm.x, lm.y, lm.z])

    cv2.imshow("Hand Landmark Extractor", frame)

    key = cv2.waitKey(1) & 0xFF

    if key == ord("s") and row is not None:

        with open(csv_file, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(row)

        print("\n✅ Sample Saved!\n")

    if key == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()