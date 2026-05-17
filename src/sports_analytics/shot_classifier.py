class ShotClassifier:
    def classify(self, pose, ball, player_pos):
        
        # Simple logic (demo ready)
        if pose["racket_high"] and ball["speed"] > 20:
            return "smash"
        
        elif ball["speed"] < 10:
            return "drop"
        
        elif pose["swing_side"] == "right":
            return "forehand"
        
        else:
            return "backhand"