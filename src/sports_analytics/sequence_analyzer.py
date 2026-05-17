class SequenceAnalyzer:
    def __init__(self):
        self.history = []

    def update(self, shot):
        self.history.append(shot)
        
        if len(self.history) > 5:
            self.history.pop(0)

        return self.detect_pattern()

    def detect_pattern(self):
        if len(self.history) < 2:
            return "none"
        
        if self.history[-2:] == ["drop", "smash"]:
            return "attack setup"
        
        if self.history[-2:] == ["backhand", "drop"]:
            return "defensive play"
        
        return "normal"