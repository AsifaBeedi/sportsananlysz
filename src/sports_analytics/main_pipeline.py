import json
import time
import os

# Ensure outputs folder exists
os.makedirs("outputs", exist_ok=True)

# ===== MODULES =====
class ShotClassifier:
    def classify(self, pose, ball, player_pos):
        if pose["racket_high"] and ball["speed"] > 20:
            return "smash"
        elif ball["speed"] < 10:
            return "drop"
        elif pose["swing_side"] == "right":
            return "forehand"
        else:
            return "backhand"


class IntentDetector:
    def detect(self, shot, player_pos, movement):
        if shot in ["smash", "forehand"] and movement == "forward":
            return "aggressive"
        elif shot == "drop" or movement == "backward":
            return "defensive"
        return "neutral"


class SequenceAnalyzer:
    def __init__(self):
        self.history = []

    def update(self, shot):
        self.history.append(shot)
        if len(self.history) > 5:
            self.history.pop(0)

        if len(self.history) >= 2:
            if self.history[-2:] == ["drop", "smash"]:
                return "attack setup"
            if self.history[-2:] == ["backhand", "drop"]:
                return "defensive play"

        return "normal"


class OpponentModel:
    def __init__(self):
        self.weak = []

    def update(self, shot, success):
        if not success:
            self.weak.append(shot)

    def get_weakness(self):
        if not self.weak:
            return "unknown"
        return max(set(self.weak), key=self.weak.count)


# ===== INITIALIZE =====
shot_classifier = ShotClassifier()
intent_detector = IntentDetector()
sequence_analyzer = SequenceAnalyzer()
opponent_model = OpponentModel()


# ===== MAIN LOOP (SIMULATION) =====
def run_pipeline():
    print("Running AI Pipeline... Press CTRL+C to stop")

    while True:
        # 🔥 Dummy data (replace later with YOLO/pose)
        pose = {"racket_high": True, "swing_side": "right"}
        ball = {"speed": 25}
        player_pos = "front"
        movement = "forward"

        # ===== AI LOGIC =====
        shot = shot_classifier.classify(pose, ball, player_pos)
        intent = intent_detector.detect(shot, player_pos, movement)
        pattern = sequence_analyzer.update(shot)

        opponent_model.update(shot, success=True)
        weakness = opponent_model.get_weakness()

        result = {
            "shot": shot,
            "intent": intent,
            "pattern": pattern,
            "weakness": weakness
        }

        # ===== SAVE OUTPUT =====
        with open("outputs/game_intelligence.json", "w") as f:
            json.dump(result, f)

        print("Updated:", result)

        time.sleep(2)


if __name__ == "__main__":
    run_pipeline()