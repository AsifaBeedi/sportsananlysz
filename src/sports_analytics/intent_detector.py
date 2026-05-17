class IntentDetector:
    def detect(self, shot, player_pos, movement):

        if shot in ["smash", "forehand"] and movement == "forward":
            return "aggressive"
        
        elif shot == "drop" or movement == "backward":
            return "defensive"
        
        return "neutral"